"""
IBM Granite Client - Supports local Ollama and watsonx.ai API.
Prioritizes local Ollama for running without API keys. Falls back to mock mode.
"""

from typing import Optional, List, Dict, Any, Callable
import os
import json
import time
import hashlib
from functools import wraps
from datetime import datetime, timedelta

from ..config.settings import get_settings
from ..config.logging_config import get_logger

logger = get_logger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (Exception,)
):
    """
    Decorator that retries a function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        retryable_exceptions: Tuple of exceptions to retry on
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        logger.error(f"{func.__name__} failed after {max_retries + 1} attempts: {e}")
                        raise

                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    time.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)

            raise last_exception

        return wrapper
    return decorator


class ResponseCache:
    """Simple in-memory cache for AI responses with TTL."""

    def __init__(self, max_size: int = 100, default_ttl: int = 3600):
        """
        Initialize the cache.

        Args:
            max_size: Maximum number of entries to cache
            default_ttl: Default time-to-live in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _generate_key(self, prompt: str, context: str, system_prompt: str = None) -> str:
        """Generate a cache key from the input parameters."""
        key_data = f"{prompt}|{context}|{system_prompt or ''}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]

    def get(self, prompt: str, context: str, system_prompt: str = None) -> Optional[str]:
        """
        Get a cached response if available and not expired.

        Returns:
            Cached response string or None
        """
        key = self._generate_key(prompt, context, system_prompt)

        if key not in self._cache:
            return None

        entry = self._cache[key]
        if datetime.utcnow() > entry['expires_at']:
            del self._cache[key]
            return None

        logger.debug(f"Cache hit for key {key[:8]}...")
        return entry['response']

    def set(self, prompt: str, context: str, response: str, system_prompt: str = None, ttl: int = None) -> None:
        """
        Cache a response.

        Args:
            prompt: The user prompt
            context: The context string
            response: The response to cache
            system_prompt: Optional system prompt
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        # Evict oldest entries if cache is full
        if len(self._cache) >= self.max_size:
            self._evict_oldest()

        key = self._generate_key(prompt, context, system_prompt)
        ttl = ttl or self.default_ttl

        self._cache[key] = {
            'response': response,
            'expires_at': datetime.utcnow() + timedelta(seconds=ttl),
            'created_at': datetime.utcnow()
        }
        logger.debug(f"Cached response for key {key[:8]}...")

    def _evict_oldest(self) -> None:
        """Evict the oldest cache entry."""
        if not self._cache:
            return

        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k]['created_at'])
        del self._cache[oldest_key]

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    def size(self) -> int:
        """Return the current cache size."""
        return len(self._cache)


# Import requests for Ollama HTTP API
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    logger.warning("requests not installed. pip install requests")

# Try to import IBM watsonx libraries (optional, for cloud deployment)
try:
    from ibm_watsonx_ai import APIClient, Credentials
    from ibm_watsonx_ai.foundation_models import ModelInference
    HAS_WATSONX = True
except ImportError:
    HAS_WATSONX = False

try:
    from langchain_ibm import ChatWatsonx, WatsonxEmbeddings
    HAS_LANGCHAIN_IBM = True
except ImportError:
    HAS_LANGCHAIN_IBM = False


class GraniteClient:
    """
    Client for IBM Granite models.

    Supports:
    1. Local Ollama server (recommended - no API key needed)
    2. IBM watsonx.ai API (cloud deployment)
    3. Mock mode (fallback for demo)

    Features:
    - Response caching for repeated queries
    - Retry with exponential backoff
    - Graceful degradation to mock mode
    """

    def __init__(self, ollama_model: str = None, enable_cache: bool = True):
        """
        Initialize the Granite client.

        Args:
            ollama_model: Ollama model name (default: from settings or 'granite3.3:2b')
            enable_cache: Enable response caching (default: True)
        """
        self.settings = get_settings()
        self._chat_model = None
        self._embeddings = None
        self._api_client = None
        self._initialized = False

        # Response cache
        self._cache = ResponseCache(max_size=100, default_ttl=3600) if enable_cache else None

        # Ollama configuration
        self._ollama_url = self.settings.ollama_url
        self._ollama_model = ollama_model or self.settings.ollama_model

        # HTTP session for connection pooling
        self._session = requests.Session() if HAS_REQUESTS else None

        # Check what's available
        self._use_ollama = self._check_ollama_available()

        if self._use_ollama:
            logger.info(f"Using Ollama model: {self._ollama_model} at {self._ollama_url}")
        else:
            logger.info("Ollama not available, checking watsonx.ai...")
            is_valid, errors = self.settings.validate()
            if not is_valid:
                logger.warning(f"watsonx.ai not configured: {errors}")
                logger.info("Running in demo mode with mock responses")

    def _check_ollama_available(self) -> bool:
        """Check if the Ollama server is running."""
        if not HAS_REQUESTS:
            logger.info("requests library not installed")
            return False

        try:
            response = self._session.get(
                f"{self._ollama_url}/api/tags",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                model_base = self._ollama_model.split(":")[0]
                if any(model_base in m for m in models):
                    logger.info(f"Ollama model '{self._ollama_model}' is available")
                else:
                    logger.warning(
                        f"Ollama is running but model '{self._ollama_model}' not found. "
                        f"Available: {models}. Pull with: ollama pull {self._ollama_model}"
                    )
                return True
            return False
        except requests.ConnectionError:
            logger.info(f"Ollama not running at {self._ollama_url}")
            return False
        except Exception as e:
            logger.warning(f"Error checking Ollama: {e}")
            return False

    @property
    def is_configured(self) -> bool:
        """Check if the client is properly configured."""
        if self._use_ollama:
            return True
        is_valid, _ = self.settings.validate()
        return is_valid and HAS_WATSONX

    @property
    def is_using_ollama(self) -> bool:
        """Check if using local Ollama server."""
        return self._use_ollama

    def initialize(self) -> bool:
        """Initialize the client."""
        if self._initialized:
            return True

        if self._use_ollama:
            if self._check_ollama_available():
                self._initialized = True
                logger.info("Granite client initialized with Ollama")
                return True
            else:
                logger.warning("Ollama became unavailable, falling back...")
                self._use_ollama = False

        if not self.is_configured:
            logger.warning("Granite client not configured. Using mock mode.")
            return False

        # Initialize watsonx.ai (cloud mode)
        try:
            credentials = Credentials(
                url=self.settings.watsonx_url,
                api_key=self.settings.watsonx_api_key
            )
            self._api_client = APIClient(credentials)

            if HAS_LANGCHAIN_IBM:
                self._chat_model = ChatWatsonx(
                    model_id=self.settings.granite_chat_model,
                    url=self.settings.watsonx_url,
                    apikey=self.settings.watsonx_api_key,
                    project_id=self.settings.watsonx_project_id,
                    params=self.settings.generation_params
                )

            self._initialized = True
            logger.info("Granite client initialized with watsonx.ai")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize watsonx.ai client: {e}")
            return False

    def generate_response(self, prompt: str, context: str = "", system_prompt: str = None, use_cache: bool = True) -> str:
        """
        Generate a response using IBM Granite.

        Args:
            prompt: User's input prompt
            context: Additional context (e.g., OBD data)
            system_prompt: Optional system prompt override
            use_cache: Whether to use cached responses (default: True)

        Returns:
            Generated response text
        """
        # Check cache first
        if use_cache and self._cache:
            cached = self._cache.get(prompt, context, system_prompt)
            if cached:
                return cached

        response = None

        # Try Ollama first
        if self._use_ollama:
            response = self._generate_ollama(prompt, context, system_prompt)
        # Try watsonx.ai
        elif self.is_configured:
            if not self._initialized:
                self.initialize()
            try:
                full_prompt = self._build_prompt(prompt, context, system_prompt)
                if self._chat_model:
                    result = self._chat_model.invoke(full_prompt)
                    response = result.content
            except Exception as e:
                logger.error(f"watsonx.ai error: {e}")

        # Fallback to mock
        if response is None:
            response = self._mock_response(prompt, context)

        # Cache the response
        if use_cache and self._cache and response:
            self._cache.set(prompt, context, response, system_prompt)

        return response

    def _generate_ollama(self, prompt: str, context: str = "", system_prompt: str = None) -> str:
        """Generate response using Ollama HTTP API."""
        if system_prompt is None:
            system_prompt = self._get_default_system_prompt()

        # Build messages for chat
        messages = [
            {"role": "system", "content": system_prompt}
        ]

        if context:
            messages.append({
                "role": "user",
                "content": f"Here is the vehicle diagnostic context:\n{context}"
            })
            messages.append({
                "role": "assistant",
                "content": "I understand. I'll analyze this OBD-II data to help answer your questions."
            })

        messages.append({"role": "user", "content": prompt})

        try:
            response = self._session.post(
                f"{self._ollama_url}/api/chat",
                json={
                    "model": self._ollama_model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": self.settings.temperature,
                        "top_p": self.settings.top_p,
                        "num_predict": self.settings.max_new_tokens,
                        "repeat_penalty": self.settings.repetition_penalty,
                    }
                },
                timeout=120
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("message", {}).get("content", "")
            else:
                logger.error(f"Ollama error: {response.status_code} - {response.text}")
                return None
        except requests.exceptions.Timeout:
            logger.error("Ollama request timed out")
            return None
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            return None

    def generate_streaming(self, prompt: str, context: str = ""):
        """Generate a streaming response."""
        if self._use_ollama:
            yield from self._generate_ollama_streaming(prompt, context)
            return

        # Mock streaming fallback
        response = self._mock_response(prompt, context)
        for word in response.split():
            yield word + " "

    def _generate_ollama_streaming(self, prompt: str, context: str = ""):
        """Generate streaming response from Ollama."""
        system_prompt = self._get_default_system_prompt()

        messages = [{"role": "system", "content": system_prompt}]
        if context:
            messages.append({"role": "user", "content": f"Context:\n{context}"})
            messages.append({"role": "assistant", "content": "I understand the context."})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self._session.post(
                f"{self._ollama_url}/api/chat",
                json={
                    "model": self._ollama_model,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": self.settings.temperature,
                        "top_p": self.settings.top_p,
                        "num_predict": self.settings.max_new_tokens,
                        "repeat_penalty": self.settings.repetition_penalty,
                    }
                },
                stream=True,
                timeout=120
            )

            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        pass

        except Exception as e:
            logger.error(f"Ollama streaming error: {e}")
            yield f"Error: {str(e)}"

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for texts."""
        if self._use_ollama:
            return self._get_ollama_embeddings(texts)

        # Return deterministic mock embeddings
        return [[hash(t) % 100 / 100.0 for _ in range(384)] for t in texts]

    def _get_ollama_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings using Ollama."""
        embeddings = []
        for text in texts:
            try:
                response = self._session.post(
                    f"{self._ollama_url}/api/embeddings",
                    json={
                        "model": self._ollama_model,
                        "prompt": text
                    },
                    timeout=30
                )
                if response.status_code == 200:
                    embedding = response.json().get("embedding", [])
                    if embedding:
                        embeddings.append(embedding)
                    else:
                        embeddings.append([hash(text) % 100 / 100.0 for _ in range(384)])
                else:
                    embeddings.append([hash(text) % 100 / 100.0 for _ in range(384)])
            except Exception as e:
                logger.error(f"Ollama embedding error: {e}")
                embeddings.append([hash(text) % 100 / 100.0 for _ in range(384)])
        return embeddings

    def clear_cache(self) -> None:
        """Clear the response cache."""
        if self._cache:
            self._cache.clear()
            logger.info("Response cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self._cache:
            return {"enabled": False}
        return {
            "enabled": True,
            "size": self._cache.size(),
            "max_size": self._cache.max_size
        }

    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text."""
        embeddings = self.get_embeddings([text])
        return embeddings[0] if embeddings else [0.0] * 384

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model configuration."""
        if self._use_ollama:
            info = {
                "backend": "ollama",
                "ollama_url": self._ollama_url,
                "model": self._ollama_model,
                "connected": True,
            }
            # Try to get model details from Ollama
            try:
                response = self._session.post(
                    f"{self._ollama_url}/api/show",
                    json={"name": self._ollama_model},
                    timeout=5
                )
                if response.status_code == 200:
                    data = response.json()
                    info["model_details"] = {
                        "family": data.get("details", {}).get("family", "unknown"),
                        "parameter_size": data.get("details", {}).get("parameter_size", "unknown"),
                        "quantization": data.get("details", {}).get("quantization_level", "unknown"),
                    }
            except Exception:
                pass
            return info
        return {
            "backend": "mock",
            "model": None,
            "connected": False,
        }

    def list_available_models(self) -> List[str]:
        """List models available on the Ollama server."""
        try:
            response = self._session.get(
                f"{self._ollama_url}/api/tags",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return [m.get("name", "") for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"Error listing Ollama models: {e}")
        return []

    def pull_model(self, model_name: str = None) -> bool:
        """Pull a model from the Ollama registry."""
        model = model_name or self._ollama_model
        try:
            logger.info(f"Pulling Ollama model: {model}...")
            response = self._session.post(
                f"{self._ollama_url}/api/pull",
                json={"name": model, "stream": False},
                timeout=600
            )
            if response.status_code == 200:
                logger.info(f"Model '{model}' pulled successfully")
                return True
            logger.error(f"Failed to pull model: {response.status_code}")
            return False
        except Exception as e:
            logger.error(f"Error pulling model: {e}")
            return False

    def _build_prompt(self, user_prompt: str, context: str = "", system_prompt: str = None) -> str:
        """Build the full prompt with system instructions."""
        if system_prompt is None:
            system_prompt = self._get_default_system_prompt()

        parts = [system_prompt]
        if context:
            parts.append(f"\n\nCONTEXT:\n{context}")
        parts.append(f"\n\nUSER QUESTION:\n{user_prompt}")
        parts.append("\n\nRESPONSE:")

        return "".join(parts)

    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt for OBD InsightBot."""
        return """You are OBD InsightBot, a friendly and knowledgeable automotive diagnostic assistant.

Your role is to help users understand their vehicle's OBD-II diagnostic data in simple, non-technical language.

Guidelines:
1. Always explain technical terms in simple language that anyone can understand
2. Be clear about the severity of any issues (critical, warning, or normal)
3. Provide practical recommendations when issues are detected
4. If you don't have information about something, say so clearly
5. Prioritize safety - always recommend professional inspection for serious issues
6. Be conversational and supportive, as users may be worried about their vehicle

Response Severity Levels:
- CRITICAL (Red): Immediate attention required - stop driving
- WARNING (Amber): Should be addressed soon
- NORMAL (Green): No immediate concern

Always be helpful and provide actionable advice."""

    def _parse_context(self, context: str) -> dict:
        """Parse the context string to extract actual metrics and fault codes."""
        result = {
            "metrics": [],
            "fault_codes": [],
            "critical_items": [],
            "warning_items": [],
            "normal_items": []
        }

        if not context:
            return result

        lines = context.split('\n')
        current_section = None

        for line in lines:
            line = line.strip()
            if "VEHICLE METRICS:" in line:
                current_section = "metrics"
            elif "FAULT CODES:" in line:
                current_section = "faults"
            elif current_section == "metrics" and line.startswith(("🔴", "🟡", "🟢", "⚪")):
                # Parse metric line: "🔴 Engine RPM: 5500 rpm (critical)"
                result["metrics"].append(line)
                if "🔴" in line or "(critical)" in line.lower():
                    result["critical_items"].append(line)
                elif "🟡" in line or "(warning)" in line.lower():
                    result["warning_items"].append(line)
                else:
                    result["normal_items"].append(line)
            elif current_section == "faults" and line.startswith("-"):
                # Parse fault line: "- P0300: Random misfire [critical]"
                if "None detected" not in line:
                    result["fault_codes"].append(line)
                    if "[critical]" in line.lower():
                        result["critical_items"].append(line)
                    elif "[warning]" in line.lower():
                        result["warning_items"].append(line)

        return result

    def _mock_response(self, prompt: str, context: str) -> str:
        """Generate a mock response for demo mode."""
        prompt_lower = prompt.lower()

        # Parse context to get actual data
        parsed = self._parse_context(context)

        # Check for queries about problems/issues - show actual data
        problem_keywords = ["wrong", "problem", "issue", "bad", "fix", "broken", "failing", "fail"]
        if any(kw in prompt_lower for kw in problem_keywords):
            return self._mock_problems_response(parsed, context)

        # More specific keyword matching to avoid false positives
        fault_keywords = ["fault code", "error code", "dtc", "diagnostic code", "trouble code"]
        code_pattern = "p0" in prompt_lower or "p1" in prompt_lower or "c0" in prompt_lower or "b0" in prompt_lower or "u0" in prompt_lower

        if any(kw in prompt_lower for kw in fault_keywords) or code_pattern:
            return self._mock_fault_code_response(context)
        elif any(kw in prompt_lower for kw in ["summary", "health", "status", "overview", "how is my", "check my", "all"]):
            return self._mock_summary_response(context)
        elif "rpm" in prompt_lower or "revolution" in prompt_lower:
            return self._mock_metric_response("engine_rpm", context)
        elif "coolant" in prompt_lower or "temperature" in prompt_lower or "overheating" in prompt_lower:
            return self._mock_metric_response("coolant_temp", context)
        elif "speed" in prompt_lower or "mph" in prompt_lower or "kph" in prompt_lower:
            return self._mock_metric_response("vehicle_speed", context)
        elif "battery" in prompt_lower or "voltage" in prompt_lower:
            return self._mock_battery_response(context)
        elif "fuel" in prompt_lower or "gas" in prompt_lower or "mileage" in prompt_lower:
            return self._mock_fuel_response(context)
        else:
            return self._mock_general_response(prompt, context)

    def _mock_problems_response(self, parsed: dict, context: str) -> str:
        """Generate response showing actual problems found in the data."""
        critical = parsed["critical_items"]
        warnings = parsed["warning_items"]
        faults = parsed["fault_codes"]

        total_issues = len(critical) + len(warnings)

        if total_issues == 0 and not faults:
            return """**Vehicle Problem Analysis**

Great news! **No significant problems detected** in your vehicle's diagnostic data.

All monitored systems are operating within normal parameters:
- ✅ No critical readings
- ✅ No warning indicators
- ✅ No fault codes stored

**Recommendations:**
- Continue with regular maintenance
- Monitor for any changes in vehicle behavior
- Your vehicle appears to be running well!

Is there a specific system you'd like me to check?"""

        response = f"""**Vehicle Problem Analysis**

Based on your OBD-II diagnostic data, here's what needs attention:

**Issues Found: {total_issues} total**

"""
        if critical:
            response += "**🔴 CRITICAL ISSUES (Immediate Attention Required):**\n"
            for i, item in enumerate(critical, 1):
                # Clean up the display
                clean_item = item.replace("🔴 ", "").replace("🟡 ", "").replace("🟢 ", "")
                response += f"{i}. {clean_item}\n"
            response += "\n"

        if warnings:
            response += "**🟡 WARNINGS (Should Be Addressed Soon):**\n"
            for i, item in enumerate(warnings, 1):
                clean_item = item.replace("🔴 ", "").replace("🟡 ", "").replace("🟢 ", "")
                response += f"{i}. {clean_item}\n"
            response += "\n"

        if faults:
            response += "**Fault Codes Stored:**\n"
            for fault in faults:
                response += f"{fault}\n"
            response += "\n"

        response += """**Recommendations:**
"""
        if critical:
            response += """- ⚠️ Address critical issues immediately
- Consider having vehicle inspected by a professional
- Avoid long trips until issues are diagnosed
"""
        elif warnings:
            response += """- Schedule a service appointment soon
- Monitor these readings for changes
- Keep an eye on dashboard warning lights
"""

        response += "\nWould you like me to explain any of these issues in more detail?"

        return response

    def _mock_summary_response(self, context: str) -> str:
        """Generate context-aware summary response with actual data."""
        # Parse context to get actual data
        parsed = self._parse_context(context)

        critical = parsed["critical_items"]
        warnings = parsed["warning_items"]
        normal = parsed["normal_items"]
        faults = parsed["fault_codes"]

        has_critical = len(critical) > 0
        has_warning = len(warnings) > 0
        has_faults = len(faults) > 0

        if has_critical:
            status = "Needs Immediate Attention"
            status_emoji = "🔴"
        elif has_warning:
            status = "Needs Attention"
            status_emoji = "🟡"
        else:
            status = "Generally Good"
            status_emoji = "🟢"

        response = f"""**Vehicle Health Summary**

**Overall Status: {status_emoji} {status}**

**Statistics:**
- Critical Issues: {len(critical)}
- Warnings: {len(warnings)}
- Normal Readings: {len(normal)}
- Fault Codes: {len(faults)}

"""
        # Show actual critical items
        if critical:
            response += "**🔴 Critical Readings:**\n"
            for item in critical:
                clean = item.replace("🔴 ", "").replace("🟡 ", "").replace("🟢 ", "")
                response += f"  • {clean}\n"
            response += "\n"

        # Show actual warnings
        if warnings:
            response += "**🟡 Warning Readings:**\n"
            for item in warnings:
                clean = item.replace("🔴 ", "").replace("🟡 ", "").replace("🟢 ", "")
                response += f"  • {clean}\n"
            response += "\n"

        # Show fault codes
        if faults:
            response += "**Fault Codes:**\n"
            for fault in faults:
                response += f"  {fault}\n"
            response += "\n"

        # Show some normal readings (limit to 5)
        if normal and not has_critical and not has_warning:
            response += "**✅ Sample Normal Readings:**\n"
            for item in normal[:5]:
                clean = item.replace("🔴 ", "").replace("🟡 ", "").replace("🟢 ", "")
                response += f"  • {clean}\n"
            if len(normal) > 5:
                response += f"  • ...and {len(normal) - 5} more normal readings\n"
            response += "\n"

        response += "**Recommendations:**\n"
        if has_critical:
            response += """- ⚠️ Have vehicle inspected immediately
- Avoid driving until critical issues are addressed
- Contact a professional mechanic
"""
        elif has_warning:
            response += """- Schedule a service appointment soon
- Monitor warning readings for changes
- Check dashboard for related warning lights
"""
        else:
            response += """- Continue regular maintenance schedule
- Vehicle is running within normal parameters
- No immediate action required
"""

        response += "\nAsk me about specific readings or fault codes for more details!"

        return response

    def _mock_fault_code_response(self, context: str) -> str:
        """Generate context-aware fault code response with actual codes."""
        parsed = self._parse_context(context)
        faults = parsed["fault_codes"]

        if faults:
            response = f"""**Fault Code Analysis**

**{len(faults)} Fault Code(s) Detected:**

"""
            for fault in faults:
                response += f"{fault}\n"

            response += """
**Understanding These Codes:**
Fault codes (DTCs) are stored by your vehicle's computer when it detects a problem:
- **P codes** - Powertrain (engine, transmission)
- **C codes** - Chassis (ABS, steering)
- **B codes** - Body (airbags, A/C)
- **U codes** - Network (communication issues)

**Severity Guide:**
- 🔴 **Critical** - Address immediately
- 🟡 **Warning** - Schedule service soon
- 🟢 **Minor** - Monitor but not urgent

**Recommendations:**
1. Don't ignore these codes - they indicate real issues
2. Have a mechanic diagnose the root cause
3. Clearing codes without fixing issues will cause them to return

Ask me about a specific code for a detailed explanation!"""
        else:
            response = """**Fault Code Analysis**

**✅ No Fault Codes Detected**

Great news! Your vehicle has no diagnostic trouble codes (DTCs) stored.

**What This Means:**
- The engine management system hasn't flagged any problems
- All monitored systems are operating within acceptable parameters
- No pending codes waiting to trigger

**Keep In Mind:**
- This doesn't guarantee everything is mechanically perfect
- Some issues may not trigger fault codes
- Previously cleared codes won't show until the issue recurs

**Recommendations:**
- Continue regular maintenance schedule
- If check engine light comes on, have it scanned promptly
- Pay attention to unusual sounds, smells, or performance changes

Ask me about your vehicle health summary for more details!"""

        return response

    def _mock_metric_response(self, metric: str, context: str) -> str:
        metrics_info = {
            "engine_rpm": """**Engine RPM Analysis**

Your engine RPM (Revolutions Per Minute) reading shows normal operation:

- **Current Reading:** Within normal range
- **Normal Idle Range:** 600-1000 RPM
- **Normal Driving Range:** 1500-4000 RPM

**What RPM Tells You:**
RPM indicates how fast your engine is spinning. Consistent, smooth RPM readings suggest your engine is running properly.

Your reading appears normal. Is there anything specific about engine performance you'd like to know?""",

            "coolant_temp": """**Coolant Temperature Analysis**

Your engine coolant temperature reading is within the normal operating range:

- **Normal Operating Range:** 195-220°F (90-105°C)

**What This Means:**
Your cooling system appears to be functioning correctly. The thermostat is regulating temperature properly.

**Recommendations:**
- Ensure coolant level is checked periodically
- Have cooling system inspected during routine maintenance

Any questions about your vehicle's cooling system?""",

            "vehicle_speed": """**Vehicle Speed Sensor Analysis**

Your vehicle speed sensor (VSS) readings appear normal:

- **Function:** Measures how fast your vehicle is traveling
- **Uses:** Speedometer, transmission shifting, cruise control, ABS

**Current Status:** Operating correctly

Your speed sensor data looks good. Let me know if you have any other questions!"""
        }
        return metrics_info.get(metric, self._mock_general_response(metric))

    def _mock_battery_response(self, context: str) -> str:
        """Generate mock battery response."""
        return """**Battery & Electrical System Analysis**

Based on your vehicle's diagnostic data:

**Current Status:** Normal Operation

- **Battery Voltage:** Within acceptable range (typically 12.4-12.7V when off, 13.7-14.7V when running)
- **Charging System:** Alternator appears to be functioning properly

**What This Means:**
Your vehicle's electrical system is operating within normal parameters. The battery is holding charge and the alternator is providing adequate power.

**Tips for Battery Health:**
- Have battery tested if vehicle is slow to start
- Check terminals for corrosion periodically
- Most batteries last 3-5 years

Would you like me to explain any specific electrical readings?"""

    def _mock_fuel_response(self, context: str) -> str:
        """Generate mock fuel system response."""
        return """**Fuel System Analysis**

Based on your vehicle's OBD-II data:

**Current Status:** Operating Normally

**Key Readings:**
- **Fuel System:** Closed loop operation (normal)
- **Fuel Trim:** Within acceptable range
- **Fuel Pressure:** Normal operating pressure

**What This Means:**
Your fuel system is functioning correctly. The engine is receiving the proper air-fuel mixture for efficient combustion.

**Fuel Efficiency Tips:**
- Maintain proper tire pressure
- Replace air filter as recommended
- Use the recommended fuel grade for your vehicle

Any specific fuel-related concerns you'd like me to address?"""

    def _mock_general_response(self, prompt: str, context: str = "") -> str:
        """Generate context-aware general response."""
        # Parse context to provide more relevant response
        has_metrics = "VEHICLE METRICS:" in context if context else False
        has_faults = "FAULT CODES:" in context and "None detected" not in context if context else False

        response = f"""Thank you for your question: "{prompt[:50]}{'...' if len(prompt) > 50 else ''}"

Based on your vehicle's OBD-II diagnostic data, here's what I can tell you:

"""
        if has_metrics:
            response += """**Available Data:**
Your uploaded diagnostic file contains vehicle sensor readings that I can analyze. I can help you understand:
- Engine performance metrics (RPM, load, temperatures)
- Emission system readings
- Fuel system status
- Various sensor values

"""
        if has_faults:
            response += """**Fault Codes Detected:**
Your vehicle has diagnostic trouble codes stored. Ask me about "fault codes" for a detailed explanation.

"""
        elif context:
            response += """**Good News:**
No fault codes were detected in your diagnostic data.

"""

        response += """**How I Can Help:**
Try asking me specific questions like:
- "What's my vehicle health summary?"
- "Explain my RPM readings"
- "What does my coolant temperature mean?"
- "Are there any fault codes?"

**Note:** I'm currently running in demo mode. For full AI-powered analysis, install Ollama and run: ollama pull granite3.3:2b

What would you like to know about your vehicle?"""

        return response
