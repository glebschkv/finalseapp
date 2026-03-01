"""
Voice Service for Speech-to-Text and Text-to-Speech.
Uses faster-whisper for STT and edge-tts (Microsoft Edge neural voices) for TTS.
Implements BR6: Speech-to-text Dictation and BR7: Voice Conversation Mode
"""

from typing import Optional, Callable, Tuple
import threading
import time
import io
import wave
import struct
import queue
import asyncio
import tempfile
import os
import sys
import atexit

from ..config.settings import get_settings
from ..config.logging_config import get_logger

logger = get_logger(__name__)

# ── Audio capture ──────────────────────────────────────────────
try:
    import sounddevice as sd
    import numpy as np
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False
    logger.warning("sounddevice/numpy not installed. Audio features limited.")

# ── Speech-to-Text (faster-whisper) ───────────────────────────
try:
    from faster_whisper import WhisperModel
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False
    logger.warning("faster-whisper not installed. STT disabled.")

# ── Text-to-Speech (edge-tts) ────────────────────────────────
try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False
    logger.warning("edge-tts not installed. TTS disabled.")


class VoiceService:
    """
    Service for voice input/output.

    STT : faster-whisper  (local, offline)
    TTS : edge-tts         (Microsoft Edge neural voices, online)

    Implements:
    - BR6.1: Basic voice dictation
    - BR6.3: Auto-stop on silence / continuous capture
    - BR6.4: Microphone permission handling
    - BR7.1: Voice session with spoken reply
    - BR7.2: Natural turn-taking
    """

    # ── Audio parameters ──────────────────────────────────────
    SAMPLE_RATE = 16_000          # 16 kHz – expected by Whisper
    CHANNELS = 1
    BLOCK_SIZE = 1024             # frames per sounddevice callback
    DTYPE = "float32"

    # VAD energy thresholds
    SPEECH_ENERGY_THRESHOLD = 0.015   # RMS above this → speech
    SILENCE_DURATION_SEC = 2.0        # seconds of silence after speech → segment end

    # Whisper settings
    WHISPER_MODEL_SIZE = "base"       # tiny | base | small | medium | large-v3
    WHISPER_DEVICE = "cpu"  # "cpu" or "cuda"
    WHISPER_COMPUTE = "float32"  # float16 for GPU, auto/float32 for CPU

    # Edge-TTS settings
    TTS_VOICE = "en-US-AriaNeural"    # Microsoft neural voice
    TTS_RATE = "+0%"                  # speech rate adjustment
    TTS_VOLUME = "+0%"                # volume adjustment

    def __init__(self):
        self.settings = get_settings()

        self._whisper_model: Optional["WhisperModel"] = None

        self._is_listening = False      # continuous-listen loop active
        self._is_speaking = False       # TTS playback in progress
        self._stop_speaking = False     # flag to interrupt TTS

        # Dictation mode state
        self._is_dictating = False      # dictation-mode loop active
        self._dictation_thread: Optional[threading.Thread] = None
        self._dictation_queue: queue.Queue = queue.Queue()

        self._listen_thread: Optional[threading.Thread] = None
        self._audio_queue: queue.Queue = queue.Queue()

        self._current_play_process: Optional['subprocess.Popen'] = None
        atexit.register(self.stop_speaking)

        self._initialize_services()

    # ──────────────────────────────────────────────────────────
    # Initialisation
    # ──────────────────────────────────────────────────────────

    def _initialize_services(self):
        """Lazy-load models so the UI stays responsive on startup."""
        # Models are loaded on first use (see _ensure_whisper)
        logger.info("VoiceService created (models load on first use)")

    @classmethod
    def preload_model(cls):
        """
        Pre-load the Whisper model before QApplication is created.

        CTranslate2 (faster-whisper's backend) crashes with a native
        segfault when it initialises after PyQt6's native libraries on
        Windows.  Call this once in main() before QApplication().
        """
        if not HAS_WHISPER:
            logger.info("faster-whisper not installed – skipping model preload")
            return

        # Try configured device/compute first
        attempts = [(cls.WHISPER_DEVICE, cls.WHISPER_COMPUTE)]

        for device, compute in attempts:
            try:
                logger.info(f"Pre-loading Whisper model '{cls.WHISPER_MODEL_SIZE}' "
                            f"(device={device}, compute={compute}) ...")
                cls._preloaded_model = WhisperModel(
                    cls.WHISPER_MODEL_SIZE,
                    device=device,
                    compute_type=compute,
                )
                logger.info(f"Whisper model pre-loaded successfully on {device}")
                return
            except Exception as e:
                logger.warning(f"Pre-load failed (device={device}, compute={compute}): {e}")

        logger.warning("Could not pre-load Whisper model with any configuration")
        cls._preloaded_model = None

    # Class-level cache for pre-loaded model
    _preloaded_model = None

    def _ensure_whisper(self):
        """Load the Whisper model if not already loaded.

        Tries the configured compute_type first, then falls back to
        float32 which is universally supported on all CPUs.
        """
        if self._whisper_model is not None:
            return
        if not HAS_WHISPER:
            raise RuntimeError("faster-whisper is not installed.")

        compute_types = [self.WHISPER_COMPUTE]
        if self.WHISPER_DEVICE == "cpu" and "float32" not in compute_types:
            compute_types.append("float32")  # safe fallback

        last_error = None
        device = self.WHISPER_DEVICE
        for ct in compute_types:
            try:
                logger.info(f"Loading Whisper model '{self.WHISPER_MODEL_SIZE}' (device={device}, compute={ct}) …")
                self._whisper_model = WhisperModel(
                    self.WHISPER_MODEL_SIZE,
                    device=device,
                    compute_type=ct,
                )
                logger.info("Whisper model ready")
                return
            except Exception as e:
                logger.warning(f"Whisper device='{device}' compute_type='{ct}' failed: {e}")
                last_error = e

        raise RuntimeError(f"Failed to load speech recognition model: {last_error}")

    # ──────────────────────────────────────────────────────────
    # Properties
    # ──────────────────────────────────────────────────────────

    @property
    def stt_available(self) -> bool:
        return HAS_WHISPER and HAS_AUDIO

    @property
    def tts_available(self) -> bool:
        return HAS_EDGE_TTS and HAS_AUDIO

    @property
    def is_available(self) -> bool:
        return self.stt_available

    @property
    def is_recording(self) -> bool:
        return self._is_listening

    @property
    def is_dictating(self) -> bool:
        return self._is_dictating

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    # ──────────────────────────────────────────────────────────
    # Microphone permission check (BR6.4)
    # ──────────────────────────────────────────────────────────

    def check_microphone_permission(self) -> Tuple[bool, str]:
        if not HAS_AUDIO:
            return False, "Audio library not installed. Please install sounddevice and numpy."
        try:
            devices = sd.query_devices()
            input_devices = [d for d in devices if d["max_input_channels"] > 0]
            if not input_devices:
                return False, "No microphone found. Please connect a microphone."
            with sd.InputStream(samplerate=self.SAMPLE_RATE, channels=1, blocksize=self.BLOCK_SIZE):
                pass
            return True, "Microphone available"
        except sd.PortAudioError as e:
            return False, f"Microphone access denied: {e}"
        except Exception as e:
            return False, f"Error accessing microphone: {e}"

    # ──────────────────────────────────────────────────────────
    # Continuous Listening  (STT – faster-whisper)
    # ──────────────────────────────────────────────────────────

    def start_listening(self, on_transcript: Callable[[str], None]) -> bool:
        """
        Begin continuous microphone listening.

        The listener captures complete speech segments (using energy-based
        VAD) and transcribes each one via faster-whisper.  After a segment
        is transcribed, listening continues automatically so the user can
        dictate follow-up utterances hands-free.

        Args:
            on_transcript: called on the **background thread** with
                           each transcribed string.

        Returns:
            True if listening started successfully.
        """
        ok, msg = self.check_microphone_permission()
        if not ok:
            logger.error(f"Cannot start listening: {msg}")
            return False

        if not HAS_WHISPER:
            logger.error("faster-whisper not installed – STT unavailable")
            return False

        if self._is_listening:
            return False

        # Ensure model is available (uses pre-loaded model)
        try:
            self._ensure_whisper()
        except RuntimeError as e:
            logger.error(f"Cannot start listening: {e}")
            return False

        self._is_listening = True
        self._listen_thread = threading.Thread(
            target=self._listen_loop,
            args=(on_transcript,),
            daemon=True,
        )
        self._listen_thread.start()
        logger.info("Continuous listening started")
        return True

    def stop_listening(self):
        """Stop the continuous listening loop."""
        self._is_listening = False
        if self._listen_thread and self._listen_thread.is_alive():
            self._listen_thread.join(timeout=3)
        self._listen_thread = None
        logger.info("Continuous listening stopped")

    # ── internal listen loop ──────────────────────────────────

    def _listen_loop(self, on_transcript: Callable[[str], None]):
        """
        Core loop: record → detect speech segment → transcribe → repeat.
        Runs on a daemon thread.
        """
        # Model should be loaded already via preload/start_listening;
        # double-check as a safety net.
        if self._whisper_model is None:
            try:
                self._ensure_whisper()
            except Exception as e:
                logger.error(f"Whisper init failed in listen loop: {e}")
                self._is_listening = False
                return

        speech_buffer: list = []     # list of np arrays of speech frames
        in_speech = False
        silence_blocks = 0
        silence_blocks_limit = int(
            self.SILENCE_DURATION_SEC * self.SAMPLE_RATE / self.BLOCK_SIZE
        )

        def _audio_cb(indata, frames, time_info, status):
            """sounddevice callback – push raw audio blocks."""
            if status:
                logger.debug(f"Audio status: {status}")
            self._audio_queue.put(indata.copy())

        try:
            with sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype=self.DTYPE,
                blocksize=self.BLOCK_SIZE,
                callback=_audio_cb,
            ):
                while self._is_listening:
                    try:
                        block = self._audio_queue.get(timeout=0.2)
                    except queue.Empty:
                        continue

                    rms = float(np.sqrt(np.mean(block ** 2)))

                    if rms >= self.SPEECH_ENERGY_THRESHOLD:
                        # Speech detected
                        if not in_speech:
                            in_speech = True
                            logger.debug("Speech start detected")
                        speech_buffer.append(block)
                        silence_blocks = 0
                    else:
                        if in_speech:
                            silence_blocks += 1
                            speech_buffer.append(block)  # keep trailing silence

                            if silence_blocks >= silence_blocks_limit:
                                # End of speech segment
                                logger.debug("Speech end detected – transcribing")
                                audio_segment = np.concatenate(speech_buffer, axis=0).flatten()
                                speech_buffer.clear()
                                in_speech = False
                                silence_blocks = 0

                                text = self._transcribe(audio_segment)
                                if text:
                                    on_transcript(text)

        except Exception as e:
            logger.error(f"Listen loop error: {e}")
        finally:
            self._is_listening = False
            # Drain queue
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except queue.Empty:
                    break

    # ── transcription ─────────────────────────────────────────

    def _transcribe(self, audio: "np.ndarray") -> str:
        """
        Transcribe a numpy float32 audio array using faster-whisper.
        Returns the concatenated text or empty string.
        """
        if self._whisper_model is None:
            return ""
        try:
            segments, _info = self._whisper_model.transcribe(
                audio,
                beam_size=5,
                language="en",
                vad_filter=True,
            )
            parts = [seg.text for seg in segments]
            transcript = " ".join(parts).strip()
            logger.info(f"Transcribed: {transcript[:80]}")
            return transcript
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""

    # ──────────────────────────────────────────────────────────
    # Text-to-Speech  (edge-tts)
    # ──────────────────────────────────────────────────────────

    def speak(self, text: str, callback: Optional[Callable[[], None]] = None):
        """
        Synthesise *text* to speech with edge-tts and play through speakers.

        Args:
            text:     The text to speak.
            callback: Optional – called when playback finishes.
        """
        if not self.tts_available:
            logger.warning("TTS not available")
            if callback:
                callback()
            return
        if self._is_speaking:
            return

        self._is_speaking = True
        self._stop_speaking = False

        thread = threading.Thread(
            target=self._speak_text,
            args=(text, callback),
            daemon=True,
        )
        thread.start()

    def _speak_text(self, text: str, callback: Optional[Callable[[], None]] = None):
        """Synthesise and play speech on a background thread using edge-tts."""
        tmp_path = None
        try:
            # edge-tts is async, so we need our own event loop on this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Write synthesised audio to a temp file
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
            os.close(tmp_fd)

            communicate = edge_tts.Communicate(
                text,
                voice=self.TTS_VOICE,
                rate=self.TTS_RATE,
                volume=self.TTS_VOLUME,
            )
            loop.run_until_complete(communicate.save(tmp_path))
            loop.close()

            if self._stop_speaking:
                return

            # ── Platform-aware playback ───────────────────────
            if sys.platform == "darwin":
                # macOS: use built-in afplay (supports MP3 natively)
                # avoids soundfile/libsndfile MP3 decoding issues
                import subprocess
                proc = subprocess.Popen(["afplay", tmp_path])
                self._current_play_process = proc
                while proc.poll() is None:
                    if self._stop_speaking:
                        proc.terminate()
                        proc.wait(timeout=2)
                        self._current_play_process = None
                        return
                    time.sleep(0.1)
                self._current_play_process = None
            else:
                # Windows / Linux: decode with soundfile and play via sounddevice
                import soundfile as sf
                audio_data, sample_rate = sf.read(tmp_path, dtype="float32")

                if self._stop_speaking:
                    return

                sd.play(audio_data, samplerate=sample_rate)
                sd.wait()

            logger.info(f"TTS completed for: {text[:60]}…")

        except Exception as e:
            logger.error(f"TTS error: {e}")
        finally:
            self._is_speaking = False
            self._stop_speaking = False
            # Clean up temp file
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            if callback:
                callback()

    def stop_speaking(self):
        """Interrupt TTS playback."""
        self._stop_speaking = True
        
        if getattr(self, "_current_play_process", None) is not None:
            try:
                self._current_play_process.terminate()
                self._current_play_process.wait(timeout=1)
            except Exception:
                pass
            self._current_play_process = None

        try:
            if 'sd' in globals():
                sd.stop()
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────
    # TTS Health Check
    # ──────────────────────────────────────────────────────────

    def check_tts(self) -> Tuple[bool, str]:
        """
        Run a quick diagnostic to verify the TTS pipeline works end-to-end.

        Checks performed:
        1. edge-tts library is importable
        2. Audio output device is available
        3. edge-tts can synthesise a short test phrase to an MP3 file
        4. The MP3 file is non-empty and can be decoded for playback
           (or played via afplay on macOS)

        Returns:
            (ok, message) – *ok* is True if TTS is fully operational.
        """
        # 1. Library availability
        if not HAS_EDGE_TTS:
            return False, "edge-tts is not installed. Install it with: pip install edge-tts"

        if not HAS_AUDIO:
            return False, "sounddevice/numpy not installed. Audio playback unavailable."

        # 2. Output device
        try:
            devices = sd.query_devices()
            output_devices = [d for d in devices if d["max_output_channels"] > 0]
            if not output_devices:
                return False, "No audio output device found. Please connect speakers or headphones."
        except Exception as e:
            return False, f"Could not query audio devices: {e}"

        # 3. Synthesise a short test phrase
        tmp_path = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
            os.close(tmp_fd)

            communicate = edge_tts.Communicate(
                "TTS check",
                voice=self.TTS_VOICE,
                rate=self.TTS_RATE,
                volume=self.TTS_VOLUME,
            )
            loop.run_until_complete(communicate.save(tmp_path))
            loop.close()

            file_size = os.path.getsize(tmp_path)
            if file_size == 0:
                return False, "edge-tts produced an empty audio file. Check your internet connection."

        except Exception as e:
            return False, f"edge-tts synthesis failed: {e}"

        # 4. Verify the audio file can be decoded / played
        try:
            if sys.platform == "darwin":
                # macOS: just confirm afplay exists
                import shutil
                if not shutil.which("afplay"):
                    return False, "macOS afplay command not found – cannot play audio."
            else:
                import soundfile as sf
                audio_data, sample_rate = sf.read(tmp_path, dtype="float32")
                if len(audio_data) == 0:
                    return False, "Decoded audio is empty – soundfile may lack MP3 codec support."
        except Exception as e:
            return False, f"Audio decoding failed: {e}"
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        logger.info("TTS health check passed")
        return True, "TTS is working properly."

    # ──────────────────────────────────────────────────────────
    # Legacy convenience aliases
    # ──────────────────────────────────────────────────────────

    # ──────────────────────────────────────────────────────────
    # Dictation Mode  (STT → text box, no auto-send)
    # ──────────────────────────────────────────────────────────

    def start_dictation_mode(self, on_transcript: Callable[[str], None]) -> bool:
        """
        Start dictation mode: record until manually stopped or 2 s silence,
        then transcribe and deliver text via *on_transcript* callback.

        Unlike continuous listening (voice-conversation mode), dictation
        mode captures a **single** speech segment and stops automatically.
        The transcribed text is intended to be placed into the input box
        without being sent.

        Args:
            on_transcript: called on the **background thread** with the
                           transcribed string when recording ends.

        Returns:
            True if dictation started successfully.
        """
        ok, msg = self.check_microphone_permission()
        if not ok:
            logger.error(f"Cannot start dictation: {msg}")
            return False

        if not HAS_WHISPER:
            logger.error("faster-whisper not installed – STT unavailable")
            return False

        if self._is_dictating or self._is_listening:
            return False

        try:
            self._ensure_whisper()
        except RuntimeError as e:
            logger.error(f"Cannot start dictation: {e}")
            return False

        self._is_dictating = True
        self._dictation_thread = threading.Thread(
            target=self._dictation_loop,
            args=(on_transcript,),
            daemon=True,
        )
        self._dictation_thread.start()
        logger.info("Dictation mode started")
        return True

    def stop_dictation_mode(self):
        """Manually stop dictation recording."""
        self._is_dictating = False
        if self._dictation_thread and self._dictation_thread.is_alive():
            self._dictation_thread.join(timeout=3)
        self._dictation_thread = None
        logger.info("Dictation mode stopped")

    def _dictation_loop(self, on_transcript: Callable[[str], None]):
        """
        Record a single speech segment, transcribe it, then stop.

        Auto-stops after SILENCE_DURATION_SEC of silence following
        detected speech, **or** when stop_dictation_mode() is called.
        """
        if self._whisper_model is None:
            try:
                self._ensure_whisper()
            except Exception as e:
                logger.error(f"Whisper init failed in dictation loop: {e}")
                self._is_dictating = False
                return

        speech_buffer: list = []
        in_speech = False
        silence_blocks = 0
        silence_blocks_limit = int(
            self.SILENCE_DURATION_SEC * self.SAMPLE_RATE / self.BLOCK_SIZE
        )

        def _audio_cb(indata, frames, time_info, status):
            if status:
                logger.debug(f"Audio status: {status}")
            self._dictation_queue.put(indata.copy())

        try:
            with sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype=self.DTYPE,
                blocksize=self.BLOCK_SIZE,
                callback=_audio_cb,
            ):
                while self._is_dictating:
                    try:
                        block = self._dictation_queue.get(timeout=0.2)
                    except queue.Empty:
                        continue

                    rms = float(np.sqrt(np.mean(block ** 2)))

                    if rms >= self.SPEECH_ENERGY_THRESHOLD:
                        if not in_speech:
                            in_speech = True
                            logger.debug("Dictation: speech start")
                        speech_buffer.append(block)
                        silence_blocks = 0
                    else:
                        if in_speech:
                            silence_blocks += 1
                            speech_buffer.append(block)

                            if silence_blocks >= silence_blocks_limit:
                                # 2 s silence after speech → auto-stop
                                logger.debug("Dictation: auto-stop on silence")
                                break

                # Transcribe whatever was captured
                if speech_buffer:
                    audio_segment = np.concatenate(speech_buffer, axis=0).flatten()
                    text = self._transcribe(audio_segment)
                    if text:
                        on_transcript(text)

        except Exception as e:
            logger.error(f"Dictation loop error: {e}")
        finally:
            self._is_dictating = False
            while not self._dictation_queue.empty():
                try:
                    self._dictation_queue.get_nowait()
                except queue.Empty:
                    break

    # ── Legacy convenience aliases ────────────────────────────

    def start_dictation(self, callback: Callable[[str], None]) -> bool:
        """Alias for start_listening (backward compat)."""
        return self.start_listening(callback)

    def stop_dictation(self):
        """Alias for stop_listening (backward compat)."""
        self.stop_listening()

    def stop_voice_mode(self):
        """Stop all voice activity."""
        self.stop_listening()
        self.stop_speaking()
        logger.info("Voice mode stopped")


# ── Singleton ───────────────────────────────────────────────
_voice_service: Optional[VoiceService] = None


def get_voice_service() -> VoiceService:
    """Get the voice service singleton."""
    global _voice_service
    if _voice_service is None:
        _voice_service = VoiceService()
    return _voice_service
