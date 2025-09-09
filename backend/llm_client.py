import os
import json
import logging
import subprocess
import time
import random
from pathlib import Path
import sys
from typing import List, Optional, Tuple
import tiktoken

# Import metrics collection (optional dependency)
try:
    from metrics_collector import record_llm_call, get_metrics_collector
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

    
# Default fallback configuration with local Qwen models as fallbacks
DEFAULT_FALLBACK_MODELS = [
    ("local", "hf.co/unsloth/Qwen3-8B-GGUF:Q4_K_M"),
    ("local", "hf.co/unsloth/Qwen3-0.6B-GGUF:Q4_K_M"),
]

def get_custom_fallback_models() -> List[Tuple[str, str]]:
    """Get custom fallback models from environment variables or use smart defaults
    
    When no custom models are specified, will automatically include installed
    local Ollama models as fallbacks based on availability
    """
    custom_models = []
    
    # Check for custom fallback configuration
    fallback_config = os.environ.get("LLM_FALLBACK_MODELS")
    if fallback_config:
        try:
            # Format: "provider1:model1,provider2:model2"
            for model_spec in fallback_config.split(","):
                provider, model = model_spec.strip().split(":", 1)
                custom_models.append((provider.strip(), model.strip()))
        except Exception as e:
            logging.warning(f"Invalid LLM_FALLBACK_MODELS format: {e}")
    
    # If no custom models and auto-fallbacks not disabled
    if not custom_models and os.environ.get("LLM_DISABLE_AUTO_FALLBACKS") != "1":
        return DEFAULT_FALLBACK_MODELS
    
    return custom_models

# Provider registry for cleaner dispatch
PROVIDERS = {
    "openrouter": lambda m, s, u, t: _call_openrouter(m, s, u, temperature=t),
    "local": lambda m, s, u, t: _call_local(m, s, u, temperature=t),
    # Alias 'ollama' to local HTTP chat endpoint(s)
    "ollama": lambda m, s, u, t: _call_local(m, s, u, temperature=t),
    "test": lambda _m, s, u, _t: _call_test_provider(s, u),
}

def call_llm(provider: str, model: str, system_prompt: str, user_prompt: str, *, 
             temperature: float = 0.2, fallback_models: Optional[List[Tuple[str, str]]] = None,
             max_retries: int = 3, retry_delay: float = 1.0, agent_name: str = "unknown") -> str:
    """
    Call a Large Language Model with fallback support and retry mechanism.

    Args:
        provider: e.g., "openrouter", "local"
        model: provider-specific model identifier
        system_prompt: system content
        user_prompt: user content
        temperature: decoding temperature
        fallback_models: List of (provider, model) tuples to try if primary fails
        max_retries: Maximum retry attempts per model
        retry_delay: Base delay between retries (with exponential backoff)

    Returns:
        str: model response text content

    Raises:
        RuntimeError: If all providers and fallbacks fail
    """
    # Use custom or default fallbacks if none provided
    if fallback_models is None:
        custom_fallbacks = get_custom_fallback_models()
        fallback_models = custom_fallbacks if custom_fallbacks else []
    
    # Allow forcing the test provider via environment for fast local runs
    force_test = os.environ.get("LLM_FORCE_TEST_PROVIDER", "").lower() in ("1", "true", "yes", "test")
    if force_test:
        logging.info("LLM client: forcing test provider due to LLM_FORCE_TEST_PROVIDER env var")
        primary_models = [("test", "mock")]
    else:
        # Primary model attempt (do not add implicit free fallbacks)
        primary_models = [(provider, model)] + (fallback_models or [])
    
    # Calculate token counts for metrics
    prompt_tokens = 0
    completion_tokens = 0
    if METRICS_AVAILABLE:
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            prompt_tokens = len(encoding.encode(system_prompt + user_prompt))
        except Exception:
            prompt_tokens = len(system_prompt.split()) + len(user_prompt.split())  # Rough estimate
    
    last_error = None
    call_start_time = time.time()
    
    for attempt_idx, (current_provider, current_model) in enumerate(primary_models):
        current_provider = (current_provider or "").lower()
        
        logging.info(f"LLM attempt {attempt_idx + 1}/{len(primary_models)}: {current_provider}/{current_model}")
        
        # Retry mechanism for each model
        for retry in range(max_retries):
            try:
                handler = PROVIDERS.get(current_provider)
                if not handler:
                    raise ValueError(f"Unsupported LLM provider: {current_provider}")
                
                # Make the actual LLM call
                response = handler(current_model, system_prompt, user_prompt, temperature)
                
                # Calculate completion tokens and record metrics
                if METRICS_AVAILABLE and agent_name != "unknown":
                    try:
                        encoding = tiktoken.get_encoding("cl100k_base")
                        completion_tokens = len(encoding.encode(response))
                    except Exception:
                        completion_tokens = len(response.split())  # Rough estimate
                    
                    call_latency = time.time() - call_start_time
                    record_llm_call(
                        agent_name=agent_name,
                        model=f"{current_provider}/{current_model}",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        latency=call_latency,
                        context={
                            "temperature": temperature,
                            "attempt": attempt_idx + 1,
                            "retry": retry + 1,
                            "system_prompt_length": len(system_prompt),
                            "user_prompt_length": len(user_prompt),
                            "response_length": len(response)
                        }
                    )
                
                return response
                    
            except Exception as e:
                last_error = e
                error_text = str(e)
                error_msg = f"LLM call failed (attempt {retry + 1}/{max_retries}) for {current_provider}/{current_model}: {error_text}"

                # Parse OpenRouter-like error codes from message, e.g., "OpenRouter API error [429]: ..."
                code_str = None
                marker = "OpenRouter API error ["
                if marker in error_text:
                    try:
                        start = error_text.index("[") + 1
                        end = error_text.index("]", start)
                        code_str = error_text[start:end].strip()
                    except Exception:
                        code_str = None

                # Decide retry policy based on error type
                lower_text = error_text.lower()
                is_timeout = ("timed out" in lower_text) or ("timeout" in lower_text)
                # 402: payment/plan required -> do not retry, move to next fallback immediately
                if code_str == "402":
                    logging.error(f"{error_msg}. Non-retryable (402). Moving to next fallback.")
                    break

                # 429 or timeout: allow only a single retry, then move on to next fallback quickly
                if code_str == "429" or is_timeout:
                    if retry < 1:  # allow 1 retry max for these transient errors
                        delay = retry_delay * (2 ** retry) + random.uniform(0, 1)
                        logging.warning(f"{error_msg}. Quick retry due to {'timeout' if is_timeout else '429'} in {delay:.2f}s...")
                        time.sleep(delay)
                        continue
                    else:
                        logging.error(f"{error_msg}. Moving to next fallback.")
                        break

                # Default retry behavior
                if retry < max_retries - 1:
                    delay = retry_delay * (2 ** retry) + random.uniform(0, 1)
                    logging.warning(f"{error_msg}. Retrying in {delay:.2f}s...")
                    time.sleep(delay)
                else:
                    logging.error(f"{error_msg}. Moving to next fallback.")
                    break
    
    # All models and retries failed
    # 1. Check if non-interactive mode or running in automation
    cont_env = os.environ.get("LLM_CONTINUE_ON_FAILURE", "").lower()
    cont_disabled = cont_env in ("0", "false", "no", "n", "off")
    auto_mode = os.environ.get("LLM_AUTO_MODE", "").lower() in ("1", "true", "yes", "y", "on")
    
    # In auto mode or when running a batch experiment, auto-retry or use fallback text
    if auto_mode or not (sys.stdin and sys.stdin.isatty()) or cont_disabled:
        # Try local models automatically without prompting
        for local_model in ["hf.co/unsloth/Qwen3-8B-GGUF:Q4_K_M", "hf.co/unsloth/Qwen3-0.6B-GGUF:Q4_K_M"]:
            try:
                logging.info(f"Auto-retrying with local model {local_model}...")
                handler = PROVIDERS.get("local")
                if handler:
                    response = handler(local_model, system_prompt, user_prompt, temperature)
                    logging.info(f"Successfully used local model {local_model} as fallback")
                    return response
            except Exception as e:
                logging.warning(f"Auto-fallback to {local_model} failed: {e}")
        
        # If all auto-fallbacks failed, return a simple response rather than crashing
        fallback_text = os.environ.get("LLM_FALLBACK_TEXT", "I need to go now. Goodbye!")
        logging.warning(f"All LLM providers failed. Using fallback text: '{fallback_text}'")
        return fallback_text
    
    # 2. Only run interactive prompt if explicitly enabled and in terminal
    if (sys.stdin and sys.stdin.isatty()) and not cont_disabled:
        sys.stderr.write(
            "\nLLM call failed after retries and fallbacks.\n"
            f"Provider/Model: {provider}/{model}\n"
            f"Agent: {agent_name}\n"
            f"Last error: {last_error}\n\n"
            "Press Enter to retry primary, 's' to skip with fallback text, or 'q' to abort.\n"
            "(Set LLM_CONTINUE_ON_FAILURE=0 to disable this prompt, or LLM_AUTO_MODE=1 for auto mode)\n"
        )
        sys.stderr.flush()
        primary_provider = (provider or "").lower()
        while True:
            try:
                choice = sys.stdin.readline().strip().lower()
            except Exception:
                choice = 'q'
            if choice in ('q', 'quit', 'exit'):
                break
            if choice in ('s', 'skip'):
                return "I need to go now. Goodbye!"
            # Try local models first on empty enter
            if not choice:
                for local_model in ["hf.co/unsloth/Qwen3-8B-GGUF:Q4_K_M", "hf.co/unsloth/Qwen3-0.6B-GGUF:Q4_K_M"]:
                    try:
                        sys.stderr.write(f"Trying local model {local_model}...\n")
                        sys.stderr.flush()
                        handler = PROVIDERS.get("local")
                        if handler:
                            response = handler(local_model, system_prompt, user_prompt, temperature)
                            return response
                    except Exception as e:
                        sys.stderr.write(f"Local model {local_model} failed: {e}\n")
                        sys.stderr.flush()
            
            # Retry primary once per loop if local models failed
            handler = PROVIDERS.get(primary_provider)
            if not handler:
                break
            try:
                call_start_time = time.time()
                response = handler(model, system_prompt, user_prompt, temperature)
                if METRICS_AVAILABLE and agent_name != "unknown":
                    try:
                        encoding = tiktoken.get_encoding("cl100k_base")
                        completion_tokens = len(encoding.encode(response))
                    except Exception:
                        completion_tokens = len(response.split())
                    call_latency = time.time() - call_start_time
                    record_llm_call(
                        agent_name=agent_name,
                        model=f"{primary_provider}/{model}",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        latency=call_latency,
                        context={"temperature": temperature, "manual_retry": True}
                    )
                return response
            except Exception as e:
                last_error = e
                sys.stderr.write(f"Retry failed: {e}\nPress Enter to retry again, 's' to skip, or 'q' to abort.\n")
                sys.stderr.flush()

    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

def _call_test_provider(system_prompt: str, user_prompt: str) -> str:
    """Test provider for unit testing"""
    if "lifecycle" in system_prompt.lower() or "csv" in user_prompt.lower():
        return "Alice,Bob"
    elif "schedule" in system_prompt.lower() or "comma separated" in user_prompt.lower():
        return "Alice,Bob"
    elif "knowledge" in system_prompt.lower():
        return '{"entities": ["test"], "relationships": []}'
    elif "introduce" in user_prompt.lower() or "new character" in user_prompt.lower():
        return '{"introduce": false}'
    else:
        return "Test response from mock LLM"


def _load_env_from_files():
    """Best-effort load of .env files into os.environ without external deps.

    Looks for .env in:
    - backend/.env (sibling of this file)
    - project_root/.env (parent of backend)
    Later files do not override existing environment variables.
    """
    try:
        here = Path(__file__).resolve()
        backend_dir = here.parent
        project_root = backend_dir.parent
        candidate_files = [backend_dir / ".env", project_root / ".env"]
        for f in candidate_files:
            if f.is_file():
                for line in f.read_text().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and (k not in os.environ):
                        os.environ[k] = v
                        if k == "OPENROUTER_API_KEY":
                            # Track source for diagnostics; do not log the key itself
                            os.environ.setdefault("LLM_ENV_SOURCE", str(f))
    except Exception:
        # Silent best-effort
        pass


def _select_ollama_endpoints_for_model(model: str) -> list:
    """Select Ollama endpoints based on model name and env vars."""
    m = (model or "").lower()
    
    # First prioritize local models that exactly match the model name
    if "hf.co/unsloth/qwen3" in m.lower() or "gguf" in m.lower():
        base = os.environ.get("OLLAMA_BASE_URL")
        if base:
            base = base.strip().rstrip("/")
            return [base + ("/api/chat" if not base.endswith("/api/chat") else "")]
        return ["http://localhost:11434/api/chat"]
    
    # Explicit per-size endpoints next
    if any(k in m for k in ["qwen3:0.6b", "qwen3-0.6b", "qwen3 0.6b", "0.6b"]):
        base = os.environ.get("OLLAMA_ENDPOINT_QWEN06B") or os.environ.get("OLLAMA_BASE_URL")
        if base:
            base = base.strip().rstrip("/")
            return [base + ("/api/chat" if not base.endswith("/api/chat") else "")]
        return ["http://localhost:11434/api/chat"]
    
    if any(k in m for k in ["qwen3:8b", "qwen3-8b", "qwen3 8b", "-8b", ":8b"]):
        base = os.environ.get("OLLAMA_ENDPOINT_QWEN8B") or os.environ.get("OLLAMA_BASE_URL")
        if base:
            base = base.strip().rstrip("/")
            return [base + ("/api/chat" if not base.endswith("/api/chat") else "")]
        # Try localhost first, then the remote server as fallback
        return ["http://localhost:11434/api/chat", "http://213.136.69.184:11434/api/chat"]
    
    # Fallback to list env
    env_endpoints = os.environ.get("LLM_LOCAL_ENDPOINTS")
    eps = []
    if env_endpoints:
        eps = [e.strip().rstrip("/") for e in env_endpoints.split(",") if e.strip()]
        return [e + ("/api/chat" if not e.endswith("/api/chat") else "") for e in eps]
    
    base = os.environ.get("OLLAMA_BASE_URL")
    if base:
        base = base.strip().rstrip("/")
        return [base + ("/api/chat" if not base.endswith("/api/chat") else "")]
    
    # Try both localhost and the remote server
    return ["http://localhost:11434/api/chat", "http://213.136.69.184:11434/api/chat"]


def _call_local(model: str, system_prompt: str, user_prompt: str, *, temperature: float = 0.2) -> str:
    """Call local Ollama server with error handling"""
    try:
        import requests
    except ImportError:
        raise RuntimeError("requests library not available for local LLM calls")
    
    # Try multiple local endpoints (can be overridden via env LLM_LOCAL_ENDPOINTS)
    local_endpoints: List[str] = _select_ollama_endpoints_for_model(model)
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt + "/no_think"},
            {"role": "user", "content": user_prompt + "/no_think"}
        ],
        "stream": False,  # Disable streaming for better error handling
        "options": {
            "temperature": temperature
        }
    }
    print(payload)
    last_error = None
    timeout_s = float(os.environ.get("LLM_LOCAL_TIMEOUT_SECONDS", "60"))
    for endpoint in local_endpoints:
        try:
            logging.info(f"Trying local LLM endpoint: {endpoint}")
            response = requests.post(endpoint, json=payload, timeout=timeout_s)
            response.raise_for_status()
            
            if endpoint.endswith("/api/chat"):  # Ollama format
                data = response.json()
                return data.get("message", {}).get("content", "")
            else:
                # Handle other local formats if needed
                return response.text
                
        except Exception as e:
            last_error = e
            logging.warning(f"Local endpoint {endpoint} failed: {str(e)}")
            continue
    
    raise RuntimeError(f"All local LLM endpoints failed. Last error: {last_error}")

def _call_openrouter(model: str, system_prompt: str, user_prompt: str, *, temperature: float = 0.2) -> str:
    """Call OpenRouter API using requests (faster than curl)."""
    if not os.environ.get("OPENROUTER_API_KEY"):
        _load_env_from_files()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set in environment.")
    if not model:
        raise ValueError("OpenRouter model must be provided.")

    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt + "/no_think"},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": float(temperature),
    }
    referer = (
        os.environ.get("OPENROUTER_REFERRER")
        or os.environ.get("OPENROUTER_REFERER")
        or os.environ.get("LLM_APP_URL")
        or "http://localhost"
    )
    app_title = os.environ.get("LLM_APP_NAME") or "GenAI Game"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": referer,
        "X-Title": app_title,
    }

    verbose = os.environ.get("LLM_VERBOSE", "0") not in ("", "0", "false", "False")
    verbose_full = os.environ.get("LLM_VERBOSE_FULL", "0") not in ("", "0", "false", "False")
    if verbose:
        try:
            logging.info(
                "LLM request -> provider=%s model=%s temp=%.2f sys_len=%d user_len=%d",
                "openrouter", model, float(temperature), len(system_prompt or ""), len(user_prompt or ""),
            )
        except Exception:
            pass

    # Increased timeout from default 5 seconds to 30 seconds for large prompt payloads
    timeout_s = float(os.environ.get("LLM_REQUEST_TIMEOUT_SECONDS", "30"))
    try:
        import requests as _requests
        resp = _requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout_s)
        if verbose:
            raw = resp.text or ""
            if verbose_full:
                logging.info("LLM raw response (FULL): %s", raw)
            else:
                logging.info("LLM raw response (first 500 chars): %s", raw[:500])
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            error_info = data.get("error") or {}
            raise RuntimeError(f"OpenRouter API error [{error_info.get('code','unknown')}]: {error_info.get('message','Unknown error')}")
        if "choices" not in data or not data["choices"]:
            raise RuntimeError("No choices returned from OpenRouter API")
        return data["choices"][0]["message"].get("content", "")
    except Exception as e:
        logging.exception("OpenRouter request failed: %s", e)
        raise


def convert_to_completion_format(messages):
    """
    Convert messages to completion format for LLM processing.
    
    Args:
        messages: List of message dictionaries with role and content
        
    Returns:
        Formatted completion string
    """
    if not messages:
        return ""
    
    completion_parts = []
    for message in messages:
        role = message.get('role', 'user')
        content = message.get('content', '')
        if role == 'system':
            completion_parts.append(f"System: {content}")
        elif role == 'user':
            completion_parts.append(f"User: {content}")
        elif role == 'assistant':
            completion_parts.append(f"Assistant: {content}")
        else:
            completion_parts.append(f"{role}: {content}")
    
    return "\n\n".join(completion_parts)

# Best-effort: load environment variables from .env files at import time
try:
    _load_env_from_files()
except Exception:
    pass
