# 1 – Introduction

## 1.1 – Project Summary

Modern vehicles generate a large volume of diagnostic data through their OBD-II (On-Board Diagnostics, Version II) systems, standardised under SAE J1979 and ISO 15031-5 [1]. These systems track metrics such as engine RPM, coolant temperature, throttle position, and diagnostic trouble codes. However, most of this data is inaccessible to the average driver. A 2024 Motorpoint study found that 76% of UK motorists wouldn't know what to do if their car broke down [2], and over half rely entirely on professional assistance for any maintenance concern. There is a clear gap between the diagnostic data a vehicle produces and the owner's ability to interpret it. We refer to this as the "diagnostic divide", and closing it became the central motivation for the project.

IBM commissioned our group to develop a solution. Our primary client contact throughout has been John McNamara, Product Owner at IBM. In early meetings with John, we discussed the target user profile: not mechanics or enthusiasts, but everyday drivers who want to know if something is wrong and what to do about it. From this, we developed OBD InsightBot, a locally-hosted desktop chatbot built with Python and PyQt6. Users upload an OBD-II log file in CSV format and can then ask questions about their vehicle's health in plain English.

The system parses the uploaded CSV, extracts key metrics (engine RPM, coolant temperature, throttle position, etc.) and any diagnostic trouble codes, then passes this data into a Retrieval-Augmented Generation (RAG) pipeline powered by IBM's Granite 3.3 language model running locally via Ollama. This means no data leaves the user's machine. We also implemented voice interaction, including speech-to-text dictation and a full voice conversation mode, as John was keen on supporting hands-free use while driving.

We set four measurable goals at the start of the project: (1) parse any valid OBD-II CSV and extract all standard metrics, (2) explain every generic diagnostic trouble code from a database of 185+ codes, (3) classify each AI response by severity using a traffic light system (critical, warning, normal), and (4) support both text and voice-based interaction. All four objectives have been met in the final build.

The remainder of this report covers the technical development of the system (Section 2), use and installation instructions (Section 3), and maintenance considerations including ethical implications (Section 4).

**References:**
[1] SAE International, "J1979: E/E Diagnostic Test Modes," SAE Standard, 2017.
[2] Motorpoint, "Three quarters of motorists wouldn't know what to do if their car broke down," 2024.
[3] Fortune Business Insights, "Automotive Diagnostic Scan Tools Market Size, Share & Industry Analysis," 2024.


## 1.2 – System Access and Setup

The source code is hosted on GitHub at:
**https://github.com/COMP2281/software-engineering-group25-26-18.git**

A copy has also been submitted via Ultra alongside this report.

**Prerequisites:**
- Python 3.8 or higher
- Ollama (https://ollama.com)
- Approximately 2 GB of free disk space for the Granite model
- A microphone (optional, only required for voice features)

**Setup steps:**

1. Clone the repository:
```
git clone https://github.com/COMP2281/software-engineering-group25-26-18.git
cd software-engineering-group25-26-18
```

2. Create and activate a virtual environment:
```
python3 -m venv venv
source venv/bin/activate          # macOS / Linux
venv\Scripts\activate             # Windows
```

3. Install dependencies:
```
pip install -r requirements.txt
```

4. Start Ollama and pull the Granite model:
```
ollama serve
ollama pull granite3.3:2b
```

5. Run the application:
```
python src/main.py
```

The application has been tested on Windows 10/11, macOS, and Ubuntu. Voice features require a working audio input device.

**Getting started:**
On launch, register a new account with a username and password, then log in. Click "New Chat" and upload an OBD-II CSV file to begin. We have included three demo log files in the repository root (demo_log.csv, demo_log_2.csv, demo_log_3.csv) for immediate testing. Once uploaded, try asking "What's wrong with my vehicle?" or "Explain fault code P0300".

Staff are free to create as many accounts as needed. Accounts and all associated data can be deleted from within the application.


## 1.3 – Behavioural Requirements Status

The table below presents the status of each behavioural requirement from our Requirements Document. We defined 29 scenarios across 8 features. Of those, 27 are fully met and 2 are not implemented. All 19 MUST-have scenarios (BR1 through BR5) are fully working. Of the 10 SHOULD-have scenarios (BR6 through BR8), 8 are fully met and 2 are not. Where a requirement has been modified from the original specification, we have noted the change and our reasoning.

See the table on the following page.

*[Table is provided in the accompanying .docx file due to Word formatting requirements]*

The two unimplemented scenarios are both SHOULD-haves. BR6.2 (inserting dictated text at the cursor position rather than appending) was deprioritised in favour of getting the core voice pipeline working reliably. BR7.3 (wake word activation) was not implemented because it would require an always-on microphone listener, which conflicts with our local-first, privacy-focused design and would increase background resource consumption.

All other modifications were intentional improvements. We switched from IBM Granite STT to faster-whisper for speech recognition (BR6.1) to keep everything running locally without an internet dependency. The silence detection threshold was reduced from 3 seconds to 2 (BR6.3, BR7.2) after user testing showed 3 seconds felt unresponsive. Chat export (BR3.4) was expanded to support JSON and Markdown alongside plain text, which we felt would be useful for developers wanting to work with the data programmatically.
