# 3 -- Use and Installation

## 3.1 -- System Requirements

OBD InsightBot runs on Windows 10/11, macOS, and Ubuntu Linux. Table 3.1 lists the minimum requirements.

| Requirement | Detail |
|---|---|
| Python | 3.8 or higher (3.11 recommended) |
| Ollama | Latest version from https://ollama.com |
| Disk space | Approximately 2 GB (for the Granite 3.3 2B model weights) |
| RAM | 4 GB minimum; 8 GB recommended for smooth inference |
| Microphone | Required only for voice features (speech dictation and voice conversation mode) |
| Internet connection | Required only during initial setup (to download dependencies and the language model) and for text-to-speech output |

The application itself does not require internet access during normal use. All AI inference, speech-to-text transcription, and data storage run locally. The only feature that contacts an external server at runtime is the text-to-speech engine (edge-tts), which sends AI-generated response text to Microsoft's neural TTS service for synthesis. No user data or vehicle diagnostics are transmitted.


## 3.2 -- Installation

Full installation instructions are provided in Section 1.2 and in the project README. In summary, the process consists of five steps:

1. Clone the repository from GitHub.
2. Create and activate a Python virtual environment.
3. Install dependencies with `pip install -r requirements.txt`.
4. Start Ollama and pull the Granite model with `ollama pull granite3.3:2b`.
5. Launch the application with `python src/main.py`.

On first launch, the application creates a local SQLite database file at `data/obd_insightbot.db` and a logs directory. No manual database setup or configuration is needed.

If Ollama is not running or the Granite model has not been downloaded, the application will start in Demo Mode. In this mode, all features remain functional but AI responses are generated from pre-built templates rather than the language model. The status bar at the bottom of the window indicates the current mode: green text for Ollama mode, amber for Demo Mode.


## 3.3 -- Account Management

### Creating an Account

When the application opens, the login screen is displayed with a dark gradient background and a central white card. To create a new account, click "Create Account" below the sign-in form. The registration form requires three fields:

- **Username**: 3 to 50 characters, letters, numbers, and underscores only.
- **Password**: minimum 6 characters.
- **Confirm Password**: must match the password field.

If any field is invalid, an error message appears immediately below the form explaining what needs to be corrected. On successful registration, a confirmation dialog appears and the form switches back to the sign-in view with the username pre-filled.

Registration is rate-limited to 3 attempts per hour to prevent abuse.

### Signing In

Enter your username and password, then click "Sign In" or press Enter. Login attempts are rate-limited to 5 per 5 minutes. If the limit is reached, the error message indicates how many seconds remain before you can try again.

On successful login, the application transitions to the main chat screen.

### Logging Out

Click the "Logout" button in the sidebar to return to the login screen. The current session is invalidated immediately.

### Deleting an Account

Account deletion is available from within the application. Deleting an account permanently removes all associated data, including every chat session and every message. This operation cannot be undone. The application prompts for password confirmation before proceeding.


## 3.4 -- Starting a New Chat

The main interface is divided into two panels: a sidebar on the left showing the chat history, and the conversation area on the right.

To begin a diagnostic session:

1. Click the "New Chat" button at the top of the sidebar.
2. A file dialog opens. Select a CSV file containing OBD-II data. The repository includes three sample files (`demo_log.csv`, `demo_log_2.csv`, `demo_log_3.csv`) for testing.
3. The application parses the CSV, extracts vehicle metrics (engine RPM, coolant temperature, vehicle speed, throttle position, engine load) and any diagnostic trouble codes (DTCs).
4. A new chat session is created and listed in the sidebar. The conversation area displays the parsed data summary.

If the CSV is invalid or does not contain recognisable OBD-II columns, an error dialog explains the problem and no chat is created.

Each chat session is tied to a single OBD-II log file. To analyse a different file, start a new chat. All previous chats remain accessible in the sidebar and can be reopened at any time.


## 3.5 -- Asking Questions

Once a chat is active, type a question in the input field at the bottom of the conversation area and press Enter or click the send button. The application supports natural language queries about the uploaded vehicle data. Useful questions include:

- "What's wrong with my vehicle?"
- "Explain fault code P0300"
- "Is my coolant temperature normal?"
- "Give me a summary of the vehicle health"
- "What should I do about the engine misfire?"

While the AI is processing, an animated "Thinking..." indicator appears in the conversation area. Responses typically take 2 to 10 seconds depending on hardware and query complexity.

### Severity Classification

Every AI response is automatically classified into one of three severity levels, displayed as a coloured indicator on the message:

| Severity | Colour | Meaning |
|---|---|---|
| Critical | Red | One or more issues require immediate attention. The system recommends professional inspection and may advise against driving. |
| Warning | Amber | Issues detected that should be investigated but are not immediately dangerous. |
| Normal | Green | No significant issues detected. The vehicle appears to be operating within expected parameters. |

The classification is determined by combining three signals: metric threshold analysis (e.g. coolant temperature above 110 C is critical), diagnostic trouble code prefix matching (e.g. P03xx misfire codes are critical), and keyword analysis of the AI response text with negation detection (to correctly handle phrases like "no critical issues found").


## 3.6 -- Chat History Management

All chat sessions are listed in the sidebar, ordered by most recent activity. Each entry shows the chat name and the last update time.

**Renaming a chat.** Right-click on a chat in the sidebar and select "Rename" from the context menu. Enter a new name (up to 100 characters) and press OK.

**Deleting a chat.** Right-click and select "Delete". A confirmation dialog appears. Deletion removes the chat and all its messages permanently.

**Exporting a chat.** Right-click and select "Export". Choose a save location and the chat is exported as a plain text file. The export includes a vehicle metrics summary, any detected fault codes, and the full conversation transcript with timestamps and severity markers.

**Copying to clipboard.** Right-click and select "Copy All" to copy the entire chat transcript to the system clipboard.

**Searching chats.** Use the search field at the top of the sidebar to filter chats by name.


## 3.7 -- Voice Features

OBD InsightBot provides two voice interaction modes, both requiring a connected microphone.

### Speech Dictation (Dictation Mode)

Click the microphone button next to the text input field. The button changes colour to indicate recording is active. Speak your question naturally. The application uses faster-whisper (a local Whisper model running on CPU) to transcribe your speech in real time. After 2 seconds of silence, recording stops automatically and the transcribed text appears in the input field. You can review and edit the text before sending.

Dictation mode does not send the message automatically. It simply converts your speech to text, giving you a chance to correct any transcription errors.

### Voice Conversation Mode

For a fully hands-free experience, start a voice conversation session. In this mode:

1. The application listens continuously for speech.
2. When you stop speaking (after 2 seconds of silence), your speech is transcribed and sent as a query automatically.
3. The AI response is read aloud using Microsoft's neural text-to-speech engine (en-US-AriaNeural voice).
4. The system then resumes listening for your next question.

This mode is designed for use when the driver cannot interact with the keyboard, for example while their vehicle is stationary but they want to keep their hands free.

### Read Aloud

Any AI response in the chat can be read aloud individually. Right-click on a message or click the speaker icon to have the text-to-speech engine read the response. Playback can be stopped at any time.

### Technical Notes on Voice

Speech-to-text runs entirely locally using the faster-whisper "base" model (74 million parameters, int8 quantisation). No audio data leaves the machine.

Text-to-speech uses Microsoft Edge's neural TTS service and requires an internet connection. Only the AI-generated response text is sent for synthesis. No user data, vehicle data, or voice recordings are transmitted.


## 3.8 -- Status Bar

The status bar at the bottom of the application window displays the current AI backend status:

| Status | Indicator | Meaning |
|---|---|---|
| Ollama connected | Green text: "AI: granite3.3:2b (Ollama)" | The local language model is running and available. All features are fully functional. |
| Demo Mode | Amber text: "AI: Demo Mode" | Ollama is not running or the model is not available. The application uses pre-built template responses instead of live AI inference. |


## 3.9 -- Sample Workflow

Table 3.9 illustrates a typical diagnostic workflow from start to finish.

| Step | Action | System Response |
|---|---|---|
| 1 | Open the application and sign in | Main chat screen loads with sidebar and conversation area |
| 2 | Click "New Chat" and select `demo_log.csv` | CSV is parsed; 5 metrics and 1 fault code (P0300) extracted. Chat appears in sidebar. |
| 3 | Type "What's wrong with my vehicle?" | AI analyses the parsed data and responds with a summary. The response is flagged as Warning or Critical depending on the severity of the detected issues. |
| 4 | Type "Explain fault code P0300" | AI provides a detailed explanation of the random cylinder misfire code, including probable causes (spark plugs, fuel injectors, ignition coils) and recommended actions. |
| 5 | Click the microphone button and say "Is my coolant temperature normal?" | Speech is transcribed to text. The transcribed question appears in the input field. Press Enter to send. |
| 6 | AI responds that coolant temperature is within the normal range (92--97 C) | Response is classified as Normal (green indicator). |
| 7 | Right-click on the chat in the sidebar and select "Export" | Chat transcript saved as a text file including metrics summary, fault codes, and full conversation. |
| 8 | Click "Logout" | Session ends. User is returned to the login screen. |


## 3.10 -- Troubleshooting

Table 3.10 covers common issues and their solutions.

| Problem | Likely Cause | Solution |
|---|---|---|
| "AI: Demo Mode" in status bar | Ollama is not running or the Granite model has not been downloaded | Run `ollama serve` in a terminal, then `ollama pull granite3.3:2b`. Restart the application. |
| Application does not start | Python version too old or missing dependencies | Verify Python 3.8+ with `python3 --version`. Re-run `pip install -r requirements.txt`. |
| CSV upload rejected | File does not contain recognised OBD-II columns | Ensure the CSV contains at least one of: engine_rpm, coolant_temp, vehicle_speed, throttle_position, engine_load, fault_codes. |
| Voice dictation not working | No microphone detected or audio dependencies missing | Check that a microphone is connected. Verify `sounddevice` and `faster-whisper` are installed. |
| Text-to-speech silent | No internet connection or speaker issue | edge-tts requires internet. Check your connection and speaker/headphone output. |
| "Rate limit exceeded" on login | Too many failed login attempts | Wait for the indicated number of seconds before trying again. The lockout window is 5 minutes. |
| Slow AI responses | Hardware limitations (CPU-only inference) | Responses on CPU typically take 2--10 seconds. Ensure no other resource-intensive processes are running. A machine with 8 GB RAM will perform noticeably better than one with 4 GB. |
| Application crashes on Windows at startup | CTranslate2/Qt native library conflict | This is a known issue. The application pre-loads the Whisper model before initialising Qt to avoid it. If the crash persists, try updating to the latest faster-whisper version. |
