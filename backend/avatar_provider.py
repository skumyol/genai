import os
import re
import json
from typing import Dict, Any, Optional

import base64
import requests


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name or "npc")


def build_avatar_prompt(npc: Dict[str, Any], world: Dict[str, Any]) -> str:
    name = npc.get("name") or "Unnamed"
    role = npc.get("role") or "villager"
    personality = npc.get("personality") or {}
    traits = ", ".join(sorted([f"{k}:{v}" for k, v in personality.items()])) if isinstance(personality, dict) else str(personality)
    world_name = (world or {}).get("name") or "Medieval Kingdom"
    style = (world or {}).get("art_style") or "illustrated fantasy portrait, painterly, rich lighting, detailed"
    prompt = (
        f"{name}, {role} in {world_name}. Portrait, upper body, facing camera, neutral background. "
        f"Traits: {traits}. Style: {style}. Cohesive avatar icon, 1:1 aspect."
    )
    return prompt


class AvatarProvider:
    def __init__(self, provider: Optional[str] = None):
        self.provider = (provider or os.environ.get("AVATAR_PROVIDER") or "openai").lower()

    def is_configured(self) -> bool:
        if self.provider == "openai":
            return bool(os.environ.get("OPENAI_API_KEY"))
        if self.provider == "stability":
            return bool(os.environ.get("STABILITY_API_KEY"))
        if self.provider == "replicate":
            return bool(os.environ.get("REPLICATE_API_TOKEN"))
        return False

    def generate_png_bytes(self, prompt: str) -> bytes:
        if self.provider == "openai":
            return self._gen_openai(prompt)
        if self.provider == "stability":
            return self._gen_stability(prompt)
        if self.provider == "replicate":
            return self._gen_replicate(prompt)
        raise RuntimeError(f"Unsupported AVATAR_PROVIDER: {self.provider}")

    def _gen_openai(self, prompt: str) -> bytes:
        # Uses Images API returning b64
        api_key = os.environ.get("OPENAI_API_KEY")
        model = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
        url = os.environ.get("OPENAI_IMAGE_URL", "https://api.openai.com/v1/images")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "prompt": prompt,
            "size": "512x512",
            "n": 1,
            "response_format": "b64_json",
        }
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        resp.raise_for_status()
        data = resp.json()
        b64 = (data.get("data") or [{}])[0].get("b64_json")
        if not b64:
            raise RuntimeError("OpenAI image API returned no image data")
        return base64.b64decode(b64)

    def _gen_stability(self, prompt: str) -> bytes:
        # Stability AI SDXL text-to-image
        api_key = os.environ.get("STABILITY_API_KEY")
        engine = os.environ.get("STABILITY_ENGINE", "stable-diffusion-xl-1024-v1-0")
        url = f"https://api.stability.ai/v1/generation/{engine}/text-to-image"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        payload = {
            "text_prompts": [{"text": prompt}],
            "cfg_scale": 7,
            "clip_guidance_preset": "FAST_BLUE",
            "height": 512,
            "width": 512,
            "samples": 1,
        }
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=120)
        resp.raise_for_status()
        js = resp.json()
        arts = (js.get("artifacts") or [])
        if not arts:
            raise RuntimeError("Stability returned no artifacts")
        b64 = arts[0].get("base64")
        if not b64:
            raise RuntimeError("Stability artifact missing base64")
        return base64.b64decode(b64)

    def _gen_replicate(self, prompt: str) -> bytes:
        # Replicate generic text-to-image (e.g., stability-ai/sdxl)
        token = os.environ.get("REPLICATE_API_TOKEN")
        # Default model: stability-ai/sdxl with a fixed version id (example; replace as needed)
        version = os.environ.get(
            "REPLICATE_MODEL_VERSION",
            "stability-ai/sdxl:3e16d8e8b20f894c2f8f8b7f1b723f1a0d40b7a8e9f2cbe2730a2e1b3b5c6d7e",
        )
        run_url = f"https://api.replicate.com/v1/predictions"
        headers = {
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
        }
        payload = {"version": version, "input": {"prompt": prompt, "width": 512, "height": 512}}
        r1 = requests.post(run_url, headers=headers, data=json.dumps(payload), timeout=30)
        r1.raise_for_status()
        pred = r1.json()
        get_url = pred.get("urls", {}).get("get")
        # Poll for completion
        for _ in range(60):
            r2 = requests.get(get_url, headers=headers, timeout=10)
            r2.raise_for_status()
            js = r2.json()
            status = js.get("status")
            if status == "succeeded":
                outputs = js.get("output") or []
                if not outputs:
                    raise RuntimeError("Replicate returned no outputs")
                img_url = outputs[0]
                img = requests.get(img_url, timeout=30)
                img.raise_for_status()
                return img.content
            if status in ("failed", "canceled"):
                raise RuntimeError(f"Replicate prediction failed: {status}")
        raise RuntimeError("Replicate prediction timed out")


def save_avatar_png(session_static_dir: str, npc_name: str, content: bytes) -> str:
    os.makedirs(session_static_dir, exist_ok=True)
    fname = f"{_safe_name(npc_name)}.png"
    fpath = os.path.join(session_static_dir, fname)
    with open(fpath, "wb") as f:
        f.write(content)
    return fname

