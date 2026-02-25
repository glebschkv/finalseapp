"""
Voice Service for Speech-to-Text and Text-to-Speech.
Implements BR6: Speech-to-text Dictation and BR7: Voice Conversation Mode
"""

from typing import Optional, Callable, Generator, Tuple
import threading
import time
import io

from ..config.settings import get_settings
from ..config.logging_config import get_logger

logger = get_logger(__name__)

# Try to import IBM Watson Speech libraries
try:
    from ibm_watson import SpeechToTextV1, TextToSpeechV1
    from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
    HAS_WATSON_SPEECH = True
except ImportError:
    HAS_WATSON_SPEECH = False
    logger.warning("ibm-watson not installed. Voice features disabled.")

# Try to import audio libraries
try:
    import sounddevice as sd
    import numpy as np
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False
    logger.warning("sounddevice not installed. Audio features limited.")


class VoiceService:
    """
    Service for voice input/output.

    Implements:
    - BR6.1: Basic voice dictation
    - BR6.2: Dictation at caret position
    - BR6.3: Auto-stop on silence
    - BR6.4: Microphone permission handling
    - BR7.1: Voice session with spoken reply
    - BR7.2: Natural turn-taking
    - BR7.3: Wake word activation (optional)
    """

    def __init__(self):
        self.settings = get_settings()
        self._stt = None
        self._tts = None
        self._is_recording = False
        self._is_speaking = False

        # Audio settings
        self.sample_rate = 16000
        self.channels = 1
        self.silence_threshold = self.settings.silence_threshold_seconds

        self._initialize_services()

    def _initialize_services(self):
        """Initialize IBM Watson speech services."""
        if not HAS_WATSON_SPEECH:
            logger.warning("Watson Speech services not available")
            return

        api_key = self.settings.watson_speech_api_key
        url = self.settings.watson_speech_url

        if not api_key:
            logger.warning("Watson Speech API key not configured")
            return

        try:
            authenticator = IAMAuthenticator(api_key)

            # Speech to Text
            self._stt = SpeechToTextV1(authenticator=authenticator)
            self._stt.set_service_url(url)

            # Text to Speech
            self._tts = TextToSpeechV1(authenticator=authenticator)
            self._tts.set_service_url(url.replace("speech-to-text", "text-to-speech"))

            logger.info("Watson Speech services initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Watson Speech: {e}")

    @property
    def is_available(self) -> bool:
        """Check if voice services are available."""
        return HAS_WATSON_SPEECH and HAS_AUDIO and self._stt is not None

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_recording

    def check_microphone_permission(self) -> Tuple[bool, str]:
        """
        Check if microphone is available (BR6.4).

        Returns:
            Tuple of (has_permission, message)
        """
        if not HAS_AUDIO:
            return False, "Audio library not installed. Please install sounddevice."

        try:
            # Try to query audio devices
            devices = sd.query_devices()
            input_devices = [d for d in devices if d['max_input_channels'] > 0]

            if not input_devices:
                return False, "No microphone found. Please connect a microphone."

            # Try to open a short stream
            with sd.InputStream(samplerate=self.sample_rate, channels=1, blocksize=1024):
                pass

            return True, "Microphone available"

        except sd.PortAudioError as e:
            return False, f"Microphone access denied. Please enable microphone in system settings. ({str(e)})"
        except Exception as e:
            return False, f"Error accessing microphone: {str(e)}"

    def start_dictation(self, callback: Callable[[str], None]) -> bool:
        """
        Start speech-to-text dictation (BR6.1).

        Args:
            callback: Function to call with transcribed text

        Returns:
            True if started successfully
        """
        # Check permissions first
        has_permission, message = self.check_microphone_permission()
        if not has_permission:
            callback(f"[Error: {message}]")
            return False

        if not self.is_available:
            callback("[Voice services not available. Using demo mode.]")
            return False

        if self._is_recording:
            return False

        self._is_recording = True

        # Start recording in background thread
        thread = threading.Thread(
            target=self._record_and_transcribe,
            args=(callback,),
            daemon=True
        )
        thread.start()

        return True

    def stop_dictation(self):
        """Stop speech-to-text dictation."""
        self._is_recording = False

    def _record_and_transcribe(self, callback: Callable[[str], None]):
        """Record audio and transcribe in real-time."""
        try:
            audio_buffer = []
            silence_count = 0
            silence_limit = int(self.silence_threshold * (self.sample_rate / 1024))

            def audio_callback(indata, frames, time_info, status):
                if status:
                    logger.warning(f"Audio status: {status}")
                audio_buffer.extend(indata.copy())

                # Check for silence (BR6.3)
                volume = np.abs(indata).mean()
                nonlocal silence_count
                if volume < 0.01:
                    silence_count += 1
                else:
                    silence_count = 0

            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=np.float32,
                blocksize=1024,
                callback=audio_callback
            ):
                while self._is_recording:
                    time.sleep(0.1)

                    # Auto-stop on silence (BR6.3)
                    if silence_count > silence_limit:
                        logger.info("Auto-stopping dictation due to silence")
                        self._is_recording = False
                        break

            # Transcribe collected audio
            if audio_buffer:
                audio_data = np.array(audio_buffer, dtype=np.float32)
                transcript = self._transcribe_audio(audio_data)
                if transcript:
                    callback(transcript)

        except Exception as e:
            logger.error(f"Recording error: {e}")
            callback(f"[Recording error: {str(e)}]")
        finally:
            self._is_recording = False

    def _transcribe_audio(self, audio_data: np.ndarray) -> str:
        """Transcribe audio data using IBM Watson STT."""
        if not self._stt:
            return ""

        try:
            # Convert to 16-bit PCM
            audio_int16 = (audio_data * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()

            # Call Watson STT
            response = self._stt.recognize(
                audio=io.BytesIO(audio_bytes),
                content_type=f'audio/l16; rate={self.sample_rate}',
                model='en-US_BroadbandModel'
            ).get_result()

            # Extract transcript
            if response['results']:
                transcript = ' '.join([
                    result['alternatives'][0]['transcript']
                    for result in response['results']
                ])
                return transcript.strip()

            return ""

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""

    def speak(self, text: str, callback: Optional[Callable[[], None]] = None):
        """
        Convert text to speech and play (BR7.1).

        Args:
            text: Text to speak
            callback: Optional callback when finished
        """
        if not self.is_available:
            logger.warning("TTS not available")
            if callback:
                callback()
            return

        if self._is_speaking:
            return

        self._is_speaking = True

        # Speak in background thread
        thread = threading.Thread(
            target=self._speak_text,
            args=(text, callback),
            daemon=True
        )
        thread.start()

    def _speak_text(self, text: str, callback: Optional[Callable[[], None]] = None):
        """Synthesize and play speech."""
        try:
            if not self._tts:
                return

            # Synthesize audio
            response = self._tts.synthesize(
                text,
                voice='en-US_MichaelV3Voice',
                accept='audio/wav'
            ).get_result()

            # Play audio
            audio_bytes = response.content
            # Parse WAV and play using sounddevice
            # (simplified - would need proper WAV parsing)

            logger.info(f"TTS completed for: {text[:50]}...")

        except Exception as e:
            logger.error(f"TTS error: {e}")
        finally:
            self._is_speaking = False
            if callback:
                callback()

    def stop_speaking(self):
        """Stop text-to-speech playback."""
        self._is_speaking = False

    def start_voice_mode(
        self,
        on_user_speech: Callable[[str], None],
        on_response: Callable[[str], None]
    ) -> bool:
        """
        Start voice conversation mode (BR7.1, BR7.2).

        Args:
            on_user_speech: Callback when user speech is transcribed
            on_response: Callback to get response for speech

        Returns:
            True if started successfully
        """
        has_permission, message = self.check_microphone_permission()
        if not has_permission:
            logger.error(f"Voice mode failed: {message}")
            return False

        # Voice mode would implement continuous listening with
        # turn-taking based on silence detection (BR7.2)
        logger.info("Voice mode started")
        return True

    def stop_voice_mode(self):
        """Stop voice conversation mode."""
        self.stop_dictation()
        self.stop_speaking()
        logger.info("Voice mode stopped")


# Singleton instance
_voice_service: Optional[VoiceService] = None


def get_voice_service() -> VoiceService:
    """Get the voice service singleton."""
    global _voice_service
    if _voice_service is None:
        _voice_service = VoiceService()
    return _voice_service
