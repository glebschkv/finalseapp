# 1 – Introduction

## 1.1 – Project Summary

With the increasing complexity of modern vehicles, a significant amount of diagnostic data is now generated through On-Board Diagnostics (OBD-II) systems, standardised under SAE J1979 and ISO 15031-5 [1]. These systems monitor everything from engine RPM and coolant temperature to exhaust emissions and fault codes, producing data that is invaluable for vehicle maintenance but largely unintelligible to the average driver. A 2024 study by Motorpoint found that 76% of UK motorists would not know what to do if their vehicle broke down [2], and with 54% relying entirely on professional assistance for any maintenance concern, there is a clear gap between the data vehicles produce and the ability of their owners to act on it. We refer to this as the "diagnostic divide". Meanwhile, the global automotive diagnostic tools market was valued at over $36 billion in 2024 [3], reflecting a growing demand for accessible diagnostic solutions — yet the vast majority of these tools are still designed for trained mechanics, not everyday users.

IBM commissioned our group to address this problem. Our primary client contact throughout the project has been John McNamara, Product Owner at IBM. Together, we set out to develop **OBD InsightBot**: a locally-hosted desktop chatbot that allows users to upload their OBD-II log files and have a natural conversation about their vehicle's health, without needing any prior mechanical knowledge.

The system parses CSV-formatted OBD-II logs, extracts key metrics (such as engine RPM, coolant temperature, and throttle position) and any diagnostic trouble codes, then feeds this data into a Retrieval-Augmented Generation (RAG) pipeline powered by IBM's Granite 3.3 language model running locally via Ollama. The result is plain-English, severity-categorised explanations that a non-technical user can understand and act upon. We also implemented voice interaction — both speech-to-text dictation and a full voice conversation mode — to support hands-free use cases.

Our measurable goals for the project were: (a) successfully parse any valid OBD-II CSV and extract all standard metrics; (b) provide explanations for all generic diagnostic trouble codes from a database of over 185 codes; (c) classify every AI response by severity using a traffic light system (critical, warning, normal); and (d) support both text and voice-based interaction for accessibility. All four of these objectives have been met in the final product.

The remainder of this report covers the technical development of the system (Section 2), user instructions for installation and use (Section 3), and maintenance considerations including ethical implications (Section 4).

**References:**
[1] SAE International, "J1979: E/E Diagnostic Test Modes," SAE Standard, 2017. Available: https://www.sae.org/standards/content/j1979_201702/
[2] Motorpoint, "Three quarters of motorists wouldn't know what to do if their car broke down," 2024. Available: https://londonlovesbusiness.com/three-quarters-of-motorists-wouldnt-know-what-to-do-if-their-car-broke-down/
[3] Fortune Business Insights, "Automotive Diagnostic Scan Tools Market Size, Share & Industry Analysis," 2024. Available: https://www.fortunebusinessinsights.com/industry-reports/automotive-diagnostic-scan-tools-market-101914


## 1.2 – System Access and Setup

The source code for OBD InsightBot is available on GitHub at:
**https://github.com/COMP2281/software-engineering-group25-26-18.git**

A copy of the code has also been submitted via Ultra alongside this report.

**Prerequisites:**
- Python 3.8 or higher
- Ollama (available at https://ollama.com)
- Approximately 2 GB of disk space for the Granite language model
- A working microphone (optional, only required for voice features)

**Installation and Setup:**

1. Clone the repository and navigate to the project directory:
```
git clone https://github.com/COMP2281/software-engineering-group25-26-18.git
cd software-engineering-group25-26-18
```

2. Create and activate a Python virtual environment:
```
python3 -m venv venv
source venv/bin/activate          # macOS / Linux
venv\Scripts\activate             # Windows
```

3. Install the required dependencies:
```
pip install -r requirements.txt
```

4. Pull the IBM Granite model through Ollama (ensure the Ollama service is running first):
```
ollama serve                    # start the Ollama service (if not already running)
ollama pull granite3.3:2b       # download the Granite 3.3 2B model (~1.5 GB)
```

5. Launch the application:
```
python src/main.py
```

The application has been tested on Windows 10/11, macOS, and Ubuntu Linux. All core features work across platforms; voice features require a functional audio input device.

**First-Time Use:**
On launch, the application presents a login screen. Register a new account by entering a username and password, then log in. To start a conversation, click "New Chat" and upload an OBD-II log file in CSV format. We have included three demo log files in the repository root (`demo_log.csv`, `demo_log_2.csv`, `demo_log_3.csv`) for immediate testing. Once uploaded, you can begin asking questions such as "What is wrong with my vehicle?" or "Explain fault code P0300".

Staff and markers are free to create as many accounts as needed. Accounts and all associated data can be deleted from within the application at any time.


## 1.3 – Behavioural Requirements Status

The table below presents the implementation status of each behavioural requirement as defined in our Requirements Document. Of the 29 total scenarios across 8 features, 27 are fully met and 2 are not met. All MUST-have requirements (BR1 through BR5, covering 19 scenarios) are fully implemented. Of the 10 SHOULD-have scenarios (BR6 through BR8), 8 are fully met and 2 are not met. Where requirements have been modified from the original specification, we have noted the change and provided justification.

| Code | Description | Priority | Status | Changed? | Justification |
|------|-------------|----------|--------|----------|---------------|
| **BR1 — Account Management** | | | | | |
| BR1.1 | User creates an account | MUST | Fully Met | Unchanged | Implemented via `AuthService.register()` with input validation, bcrypt password hashing (12 rounds), and rate limiting (3 registrations per hour). |
| BR1.2 | User logs in to their account | MUST | Fully Met | Unchanged | `AuthService.login()` verifies credentials, generates a secure session token, and enforces rate limiting (5 attempts per 5 minutes). |
| BR1.3 | User logs out | MUST | Fully Met | Unchanged | `AuthService.logout()` invalidates the session token and redirects to the login screen. |
| BR1.4 | User deletes their account | MUST | Fully Met | Unchanged | `AuthService.delete_account()` requires password confirmation and cascade-deletes all associated chats and messages. |
| **BR2 — New Chat with Log Upload** | | | | | |
| BR2.1 | Upload a valid OBD-II CSV log | MUST | Fully Met | Unchanged | `OBDParser` validates and parses the CSV, extracting 10+ metric types and identifying fault codes from a database of 185+ entries. |
| BR2.2 | Reject invalid file types | MUST | Fully Met | Unchanged | File extension is validated before parsing; non-CSV files receive a clear error message. |
| BR2.3 | Handle valid file type with bad data | MUST | Fully Met | Unchanged | The parser detects missing OBD-II columns and corrupt data, returning descriptive error messages for each case. |
| BR2.4 | Unauthenticated user cannot start a chat | MUST | Fully Met | Unchanged | Enforced architecturally — the `MainWindow` only displays the chat screen after a successful login via `QStackedWidget`. |
| **BR3 — Chat History Management** | | | | | |
| BR3.1 | View chat history | MUST | Fully Met | Unchanged | `ChatService.get_user_chats()` retrieves all chats ordered by most recent, displayed in a sidebar list. |
| BR3.2 | Delete chat history | MUST | Fully Met | Unchanged | `ChatService.delete_chat()` supports single and batch deletion with a confirmation dialog. |
| BR3.3 | Rename a chat | MUST | Fully Met | Unchanged | Implemented via context menu using `QInputDialog` for inline renaming. |
| BR3.4 | Export a chat log | MUST | Fully Met | Modified | Now supports three export formats — plain text, JSON, and Markdown — exceeding the original specification which did not define specific formats. |
| **BR4 — General Vehicle Status Queries** | | | | | |
| BR4.1 | Summary when all metrics are normal | MUST | Fully Met | Unchanged | The RAG pipeline generates a health summary confirming normal status with specific metric readings. |
| BR4.2 | Summary when metrics are abnormal | MUST | Fully Met | Unchanged | Abnormal metrics are flagged with severity classification; the response highlights issues and provides recommendations. |
| BR4.3 | Query about unavailable data | MUST | Fully Met | Unchanged | The system clearly states when requested data is not present in the uploaded log file. |
| **BR5 — Fault Code Explanation** | | | | | |
| BR5.1 | Explain a specific generic fault code | MUST | Fully Met | Unchanged | Fault codes are looked up in `OBDParser.FAULT_CODE_DATABASE` (185+ codes) and explained via the RAG pipeline with descriptions, severity, and possible causes. |
| BR5.2 | Summary of all fault codes in log | MUST | Fully Met | Unchanged | All detected fault codes are listed with their severity and descriptions. |
| BR5.3 | Handle manufacturer-specific fault codes | MUST | Fully Met | Unchanged | Codes with manufacturer-specific prefixes are identified and the system explains that only generic OBD-II codes are supported. |
| BR5.4 | No fault codes present in log | MUST | Fully Met | Unchanged | The system provides positive reassurance and recommends continued regular maintenance. |
| **BR6 — Speech-to-Text Dictation** | | | | | |
| BR6.1 | Basic voice dictation | SHOULD | Fully Met | Modified | Uses `faster-whisper` (local Whisper inference) rather than IBM Granite STT. This change was made to enable fully offline operation and preserve data privacy — all voice processing stays on the user's machine. |
| BR6.2 | Continue dictation from caret position | SHOULD | Not Met | — | Dictated text is appended to the end of the input field rather than inserted at the caret position. We prioritised the core dictation and voice conversation functionality over this refinement. |
| BR6.3 | Auto-stop recording after silence | SHOULD | Fully Met | Modified | Auto-stop triggers after 2 seconds of silence (`SILENCE_DURATION_SEC = 2.0`) rather than the 3 seconds suggested in the original specification. We reduced this threshold after user testing showed 2 seconds felt more responsive without causing premature cut-offs. |
| BR6.4 | Handle microphone permission denied | SHOULD | Fully Met | Unchanged | `VoiceService.check_microphone_permission()` verifies device availability and provides actionable error messages if access is denied. |
| **BR7 — Voice Conversation Mode** | | | | | |
| BR7.1 | Voice session with spoken reply | SHOULD | Fully Met | Unchanged | Full pipeline implemented: microphone capture via `faster-whisper`, AI response via Granite, and spoken reply via `edge-tts` (Microsoft neural voices). |
| BR7.2 | Natural turn-taking with silence detection | SHOULD | Fully Met | Modified | Uses the same 2-second silence threshold as BR6.3. We also implemented a half-duplex turn-taking protocol to prevent the microphone from picking up TTS playback, which would otherwise create a feedback loop. |
| BR7.3 | Wake word activation | SHOULD | Not Met | — | Not implemented. Voice mode is activated via a button press in the UI. Reliable wake word detection would require an always-on microphone listener and a dedicated keyword spotting model, which conflicted with our privacy-first design approach and would have increased resource consumption significantly. |
| **BR8 — Danger Level Categorisation** | | | | | |
| BR8.1 | Critical issues shown in red | SHOULD | Fully Met | Unchanged | `SeverityClassifier` identifies critical conditions through keyword analysis, fault code prefix matching (e.g. P03xx misfire codes), and metric threshold checking. Messages are displayed with red styling and a "Critical" badge. |
| BR8.2 | Warnings shown in amber | SHOULD | Fully Met | Unchanged | Warning conditions are detected via keyword and metric analysis. The classifier uses negation-aware detection to reduce false positives (e.g. "no critical issue" is not flagged as critical). |
| BR8.3 | Normal information shown in green | SHOULD | Fully Met | Unchanged | Normal responses receive green styling. The classifier uses a scoring threshold — a strong normal signal can override minor warning keywords to prevent unnecessary alarm. |

In summary, every modification we made was a deliberate design decision rather than a scope reduction. The switch from IBM Granite STT to faster-whisper was driven by our commitment to local-first, privacy-respecting operation. The adjusted silence thresholds came directly from user testing. The two unmet scenarios (BR6.2 and BR7.3) were deprioritised in favour of delivering robust core voice functionality within our development timeline, and neither affects the primary use case of the application.
