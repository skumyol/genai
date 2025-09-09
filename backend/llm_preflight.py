#!/usr/bin/env python3
"""
Preflight LLM endpoint checks for experiments.

Reads the experimental config, enumerates all provider/model pairs used by the
selected experiments, and performs a minimal test call against each unique pair.

If any check fails, exits non-zero with a concise error message to prevent
starting long-running experiments that would later fail.

Usage:
  python llm_preflight.py --config experimental_config_six.json [--experiment EXP]
"""

import argparse
import json
import os
import sys
from typing import Dict, Any, List, Set, Tuple

# Ensure local imports resolve when invoked from scripts
sys.path.insert(0, os.path.dirname(__file__))

from llm_client import call_llm
import requests


def _collect_pairs(cfg: Dict[str, Any], experiment: str = None) -> List[Tuple[str, str, str]]:
    pairs: List[Tuple[str, str, str]] = []  # (provider, model, source)
    experiments = cfg.get("experiments", {})
    for exp_key, exp in experiments.items():
        if experiment and exp_key != experiment:
            continue
        for var in exp.get("variants", []):
            src = f"{exp_key}:{var.get('id')}"
            vcfg = var.get("config", {})
            # top-level provider/model (often summarizer)
            if vcfg.get("llm_provider") and vcfg.get("llm_model"):
                pairs.append((str(vcfg["llm_provider"]).lower(), str(vcfg["llm_model"]), src))
            # per-agent models
            for section in ("social_agents", "game_agents"):
                for _aname, acfg in (vcfg.get(section, {}) or {}).items():
                    prov = str(acfg.get("provider") or "").lower()
                    model = str(acfg.get("model") or "")
                    if prov and model:
                        pairs.append((prov, model, src))
    return pairs


def _unique_pairs(pairs: List[Tuple[str, str, str]]) -> List[Tuple[str, str, Set[str]]]:
    key_to_sources: Dict[Tuple[str, str], Set[str]] = {}
    for prov, model, src in pairs:
        key = (prov, model)
        key_to_sources.setdefault(key, set()).add(src)
    return [(prov, model, sources) for (prov, model), sources in key_to_sources.items()]


def _ollama_quick_check(model: str) -> Tuple[bool, str]:
    # Choose endpoint based on model size (0.6B -> localhost, 8B -> server), with env overrides
    m = (model or "").lower()
    base_list: List[str] = []
    if any(k in m for k in ["qwen3:0.6b", "qwen3-0.6b", "0.6b"]):
        base = os.environ.get("OLLAMA_ENDPOINT_QWEN06B") or "http://localhost:11434"
        base_list.append(base.rstrip("/"))
    elif any(k in m for k in ["qwen3:8b", "qwen3-8b", "-8b", ":8b"]):
        base = os.environ.get("OLLAMA_ENDPOINT_QWEN8B") or os.environ.get("OLLAMA_BASE_URL") or "http://213.136.69.184:11434"
        base_list.append(base.rstrip("/"))
    else:
        env_endpoints = os.environ.get("LLM_LOCAL_ENDPOINTS")
        if env_endpoints:
            for e in env_endpoints.split(","):
                e = e.strip()
                if e:
                    base_list.append(e.rstrip("/"))
        else:
            base = os.environ.get("OLLAMA_BASE_URL", "http://213.136.69.184:11434").strip().rstrip("/")
            base_list.append(base)

    timeout = float(os.environ.get("LLM_LOCAL_TIMEOUT_SECONDS", "15"))
    last_err = ""
    for base in base_list:
        try:
            tags_url = base + "/api/tags"
            r = requests.get(tags_url, timeout=timeout)
            r.raise_for_status()
            data = r.json() if r.headers.get("Content-Type", "").startswith("application/json") else {}
            models = [m.get("model") or m.get("name") for m in data.get("models", [])]
            if model in models:
                return True, f"model available at {tags_url}"
            # Not listed; still treat endpoint reachable
            return True, f"endpoint reachable ({tags_url}); model not listed"
        except Exception as e:
            last_err = str(e)
            continue
    return False, last_err or "no endpoints reachable"


def preflight(config_path: str, experiment: str = None) -> int:
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    pairs = _unique_pairs(_collect_pairs(cfg, experiment))
    if not pairs:
        print("No provider/model pairs found in config; nothing to check.")
        return 0

    print("Preflight: checking LLM endpoints (provider/model)")
    failures: List[str] = []

    for prov, model, sources in pairs:
        label = f"{prov}/{model}"
        try:
            print(f"  Checking {label} ...")
            # Fast path for Ollama: hit /api/tags first
            if prov == "ollama":
                ok, info = _ollama_quick_check(model)
                if ok:
                    print(f"  OK  - {label} (quick-check: {info})")
                    continue
                else:
                    print(f"  WARN- {label} quick-check failed: {info}; attempting minimal chat call...")
            # Minimal prompt to verify basic connectivity/credentials
            _ = call_llm(
                prov,
                model,
                system_prompt="health-check",
                user_prompt="ping",
                temperature=0.01,
                fallback_models=[],
                max_retries=1,
                retry_delay=0.5,
                agent_name="preflight",
            )
            print(f"  OK  - {label} (used by: {', '.join(sorted(sources))})")
        except Exception as e:
            failures.append(f"  ERR - {label} (used by: {', '.join(sorted(sources))}) -> {e}")

    if failures:
        print("\nPreflight failures:", file=sys.stderr)
        for f in failures:
            print(f, file=sys.stderr)
        return 2

    print("All LLM endpoints passed preflight.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Preflight LLM endpoint checks")
    ap.add_argument("--config", required=True, help="Path to experiment config JSON")
    ap.add_argument("--experiment", default=None, help="Restrict check to a single experiment key")
    args = ap.parse_args()
    rc = preflight(args.config, args.experiment)
    sys.exit(rc)


if __name__ == "__main__":
    main()
