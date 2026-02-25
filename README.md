# OBD InsightBot

**Conversational Vehicle Diagnostics Powered by IBM Granite**

A desktop app that helps you understand your vehicle's OBD-II diagnostic data through simple conversations. Runs entirely on your machine using Ollama.

---

## Quick Start

### 1. Install Ollama

Download and install Ollama from [ollama.com](https://ollama.com/download), then pull the Granite model:

```bash
ollama pull granite3.3:2b
```

Verify it's running:
```bash
ollama list
```

### 2. Set Up the App

**Windows (PowerShell)**
```powershell
git clone https://github.com/glebschkv/testcecw.git
cd testcecw
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python src/main.py
```

**macOS / Linux**
```bash
git clone https://github.com/glebschkv/testcecw.git
cd testcecw
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

---

## How the AI Works

The app supports multiple modes, chosen automatically:

| Mode | When | Requirements |
|------|------|-------------|
| **Ollama (Recommended)** | Ollama is running with `granite3.3:2b` | [Ollama](https://ollama.com) installed |
| **Cloud (Optional)** | IBM watsonx.ai API credentials configured | `pip install ibm-watsonx-ai langchain-ibm` |
| **Demo Mode (Fallback)** | Neither available | None - uses smart mock responses |

### Ollama Mode (Recommended)
Runs IBM Granite models locally via Ollama. No API keys needed, works offline, and keeps your data private.

### Demo Mode
If Ollama isn't running, the app automatically falls back to demo mode:
- Parses and displays your real OBD-II data
- Shows actual metrics, fault codes, and warnings
- Provides context-aware mock responses based on your vehicle's data

---

## What You Can Do

1. **Create Account** - Register and log in
2. **Upload OBD-II Log** - Click "+ New Chat" and select your CSV file
3. **Ask Questions** - Examples:
   - "What's wrong with my vehicle?"
   - "Give me a health summary"
   - "Explain fault code P0300"
   - "Is my engine temperature normal?"
   - "Show me all issues"

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Shift+Enter` | New line |
| `Ctrl+N` | New chat |
| `Escape` | Cancel AI response |

---

## Configuration

Copy `.env.example` to `.env` to customize settings:

```bash
cp .env.example .env
```

Key settings:
```env
# Ollama (default - no changes needed if using defaults)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=granite3.3:2b

# Optional: IBM watsonx.ai cloud credentials
# WATSONX_API_KEY=your-api-key
# WATSONX_PROJECT_ID=your-project-id
```

---

## Requirements

- Python 3.8 or higher
- [Ollama](https://ollama.com) (recommended, for local AI)
- ~1.5 GB disk space for the Granite 3.3 2B model

---

## Optional Packages

| Package | Purpose | Install Command |
|---------|---------|-----------------|
| ibm-watsonx-ai | Cloud AI (watsonx) | `pip install ibm-watsonx-ai langchain-ibm ibm-watson` |
| pyaudio | Voice input | `pip install pyaudio` |

---

## Troubleshooting

### Ollama not detected
Make sure Ollama is running:
```bash
# Start the Ollama server
ollama serve

# In another terminal, verify:
curl http://localhost:11434/api/tags
```

### Model not found
Pull the required model:
```bash
ollama pull granite3.3:2b
```

### "python is not recognized"
Download Python from https://www.python.org/downloads/ and check "Add to PATH" during install.

### "No module named PyQt6"
```bash
pip install PyQt6
```

### App won't start
Make sure virtual environment is activated:
```bash
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.8+ |
| GUI | PyQt6 |
| AI | IBM Granite 3.3 (local via Ollama) |
| Database | SQLite (SQLAlchemy) |
| Vector Store | ChromaDB |
| RAG | LangChain |

---

## License

University software engineering course project - Group 18
