#!/usr/bin/env python3
"""
Quick test script to verify Ollama connectivity and Granite model availability.
Run: python scripts/test_granite.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_requests_installed():
    """Check if requests library is installed."""
    print("Checking if requests is installed...")
    try:
        import requests
        print(f"  requests version: {requests.__version__}")
        return True
    except ImportError:
        print("  requests is not installed.")
        print("  Install with: pip install requests")
        return False


def check_ollama_running():
    """Check if Ollama server is running."""
    import requests
    from src.config.settings import get_settings
    settings = get_settings()

    url = settings.ollama_url
    print(f"\nChecking Ollama server at {url}...")

    try:
        response = requests.get(f"{url}/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            print(f"  Ollama is running! Available models: {models}")
            return True, models
        else:
            print(f"  Ollama responded with status {response.status_code}")
            return False, []
    except requests.ConnectionError:
        print(f"  Ollama is not running at {url}")
        print("  Start it with: ollama serve")
        return False, []


def check_model_available(models):
    """Check if target Granite model is available."""
    from src.config.settings import get_settings
    settings = get_settings()

    target = settings.ollama_model
    print(f"\nChecking for model '{target}'...")

    model_base = target.split(":")[0]
    if any(model_base in m for m in models):
        print(f"  Model '{target}' is available!")
        return True
    else:
        print(f"  Model '{target}' not found.")
        print(f"  Pull it with: ollama pull {target}")
        return False


def test_generation():
    """Test a simple generation with Ollama."""
    import requests
    from src.config.settings import get_settings
    settings = get_settings()

    print(f"\nTesting generation with {settings.ollama_model}...")
    try:
        response = requests.post(
            f"{settings.ollama_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "What is an OBD-II fault code? Answer in one sentence."},
                ],
                "stream": False,
                "options": {"num_predict": 100}
            },
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("message", {}).get("content", "")
        print(f"  Generation successful!")
        print(f"\n  Response: {content[:200]}")
        return True
    except Exception as e:
        print(f"  Error during generation: {e}")
        return False


def main():
    print("=" * 50)
    print("OBD InsightBot - Ollama Granite Model Test")
    print("=" * 50)

    # Check dependencies
    if not check_requests_installed():
        sys.exit(1)

    # Check Ollama server
    running, models = check_ollama_running()
    if not running:
        print("\nOllama is not running. Start it and try again.")
        sys.exit(1)

    # Check model
    if not check_model_available(models):
        sys.exit(1)

    # Test generation
    if not test_generation():
        sys.exit(1)

    print("\n" + "=" * 50)
    print("All checks passed! Ready to run OBD InsightBot.")
    print("=" * 50)
    print("\nRun the app with: python -m src.main")


if __name__ == "__main__":
    main()
