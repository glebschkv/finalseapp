# 1 – Introduction

## 1.1 – Project Summary

Modern vehicles produce a huge amount of diagnostic data through their OBD-II (On-Board Diagnostics, Version II) systems — everything from engine RPM and coolant temperatures to fault codes and emission readings, all standardised under SAE J1979 and its international equivalent ISO 15031-5 [1]. The problem is, most people have no idea what any of it means. A 2024 Motorpoint study found that 76% of UK motorists wouldn't know what to do if their car broke down [2], and over half rely entirely on a mechanic for any maintenance concern at all. So there's this gap between what the car is telling you and what you can actually do with that information. We started calling it the "diagnostic divide" pretty early on in the project and it became the core motivation behind everything we built.

IBM approached us to try and solve this problem. Our client contact throughout has been John McNamara, who is a Product Owner at IBM. In our initial meetings with John, we talked a lot about who this application was really for — not mechanics, not car enthusiasts, but everyday drivers who just want to know if something's wrong and what they should do about it. That's where OBD InsightBot came from. It's a desktop chatbot built with Python and PyQt6 that lets you upload an OBD-II log file and have a proper conversation about what's going on with your vehicle, all in plain English.

Under the hood, the system parses CSV-formatted OBD-II data, pulls out key metrics like engine RPM, coolant temperature, and throttle position, and picks up any diagnostic trouble codes. All of that gets fed into a RAG (Retrieval-Augmented Generation) pipeline that uses IBM's Granite 3.3 model, running locally through Ollama so nothing leaves the user's machine. We also added voice interaction — speech-to-text for dictation and a full voice conversation mode — because John was keen on the idea of hands-free use while driving.

Going into the project we set ourselves four concrete goals: parse any valid OBD-II CSV and extract all standard metrics; explain every generic diagnostic trouble code from a database of 185+ codes; classify each response using our traffic light system (critical, warning, normal) so users immediately know how serious something is; and support both text and voice interaction. We're happy to say all four have been met in the final build.

The rest of this report is structured as follows: Section 2 covers the technical development, Section 3 provides full use and installation instructions, and Section 4 discusses maintenance and the ethical implications of the system.

**References:**
[1] SAE International, "J1979: E/E Diagnostic Test Modes," SAE Standard, 2017.
[2] Motorpoint, "Three quarters of motorists wouldn't know what to do if their car broke down," 2024.
[3] Fortune Business Insights, "Automotive Diagnostic Scan Tools Market Size, Share & Industry Analysis," 2024.


## 1.2 – System Access and Setup

The full source code is hosted on GitHub at:
**https://github.com/COMP2281/software-engineering-group25-26-18.git**

A copy has also been submitted via Ultra alongside this report.

To get the application running, you'll need the following:
- Python 3.8 or higher
- Ollama (https://ollama.com)
- Around 2 GB of free disk space for the Granite model download
- A microphone (only if you want to use the voice features)

**Setup steps:**

1. Clone the repository:
```
git clone https://github.com/COMP2281/software-engineering-group25-26-18.git
cd software-engineering-group25-26-18
```

2. Set up a virtual environment:
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

We've tested this on Windows 10/11, macOS, and Ubuntu and it works across all three. Voice features obviously need a working audio input device.

**Getting started:**
When the application opens you'll see a login screen — just register a new account with a username and password, then log in. To start chatting, hit "New Chat" and upload an OBD-II CSV file. We've included three demo logs in the root of the repo (demo_log.csv, demo_log_2.csv, demo_log_3.csv) so you can get going straight away without needing your own data. Once the file's uploaded, try asking something like "What's wrong with my vehicle?" or "Explain fault code P0300" and the system will respond.

Feel free to create as many accounts as you need — they can all be deleted from within the app.


## 1.3 – Behavioural Requirements Status

Below is a summary of where each behavioural requirement stands in the final build. We defined 29 scenarios across 8 features in the Requirements Document. Of those, 27 have been fully met and 2 have not been implemented. Every single MUST-have requirement (BR1 through BR5 — 19 scenarios in total) is fully working. Out of the 10 SHOULD-have scenarios across BR6, BR7, and BR8, we got 8 done. Where we've changed something from the original spec, we've noted what changed and why.

See the table on the following page.

*[Table is provided in the accompanying .docx file due to Word formatting requirements]*

The two scenarios we didn't implement (BR6.2 and BR7.3) were both SHOULD-haves that we made a conscious decision to deprioritise. BR6.2 — inserting dictated text at the cursor position — was a nice-to-have refinement but we focused our time on getting the core voice pipeline working properly instead. BR7.3 — wake word activation — would've needed an always-on microphone listener running in the background, which goes against the privacy-first approach we took with the rest of the system. We felt it was better to stick with a simple button press to start voice mode.

Worth noting that the changes we did make were all intentional improvements, not cuts. Switching from IBM Granite STT to faster-whisper for speech recognition (BR6.1) was because we wanted everything to run locally without needing an internet connection. Adjusting the silence threshold from 3 seconds down to 2 (BR6.3, BR7.2) came out of our own testing — 3 seconds felt too slow and users kept thinking the system had frozen. And expanding chat export to support JSON and Markdown on top of plain text (BR3.4) was just something we thought would be useful, especially for developers who might want to look at the data programmatically.
