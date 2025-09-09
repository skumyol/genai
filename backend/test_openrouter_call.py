#!/usr/bin/env python3
"""
Simple OpenRouter chat completion test using requests and .env.

Usage:
  python test_openrouter_call.py --model qwen/qwen3-32b --prompt "What is the meaning of life?"

Reads OPENROUTER_API_KEY (and optional OPENROUTER_REFERRER/LLM_APP_URL, LLM_APP_NAME) from:
  - backend/.env
  - project_root/.env
without requiring python-dotenv.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

import requests


def load_env_best_effort():
    here = Path(__file__).resolve()
    backend_dir = here.parent
    project_root = backend_dir.parent
    for f in (backend_dir / ".env", project_root / ".env"):
        if f.is_file():
            for line in f.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and (k not in os.environ):
                    os.environ[k] = v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="OpenRouter model id (e.g., qwen/qwen3-32b)")
    ap.add_argument("--prompt", required=True, help="User prompt text")
    ap.add_argument("--timeout", type=float, default=60.0, help="Request timeout in seconds")
    args = ap.parse_args()

    load_env_best_effort()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY is not set (set it in backend/.env)", file=sys.stderr)
        sys.exit(2)

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    # Optional headers for reliability and ranking
    referer = os.environ.get("OPENROUTER_REFERRER") or os.environ.get("OPENROUTER_REFERER") or os.environ.get("LLM_APP_URL")
    app_title = os.environ.get("LLM_APP_NAME")
    if referer:
        headers["HTTP-Referer"] = referer
    if app_title:
        headers["X-Title"] = app_title

    payload = {
        "model": args.model,
        "messages": [
            {"role": "user", "content": args.prompt},
        ],
    }

    t0 = time.time()
    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=args.timeout)
    elapsed = time.time() - t0
    print(f"Status: {resp.status_code} | Time: {elapsed:.2f}s")
    try:
        data = resp.json()
    except Exception:
        print(resp.text)
        sys.exit(1 if resp.status_code >= 400 else 0)

    if resp.status_code >= 400:
        print(json.dumps(data, indent=2))
        sys.exit(1)

    # Print first choice content
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content")
    print("Response: \n" + (content or "<no content>"))


if __name__ == "__main__":
    main()

