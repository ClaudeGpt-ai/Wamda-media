#!/usr/bin/env python3
"""Generate images from a text prompt using free providers.

Providers (tried in this order with --provider auto):
  pollinations  Free, no account or key. https://image.pollinations.ai
  hf            Hugging Face free tier (FLUX.1-schnell). Needs a free HF_TOKEN.

Standard library only. Each image is saved with a JSON sidecar that records
the prompt, seed, size and provider so a result can be reproduced.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ASPECTS = {
    "1:1": (1024, 1024),
    "16:9": (1344, 768),
    "9:16": (768, 1344),
    "4:3": (1152, 864),
    "3:4": (864, 1152),
    "3:2": (1216, 832),
    "2:3": (832, 1216),
}

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}?{query}"
HF_URL = "https://router.huggingface.co/hf-inference/models/{model}"
HF_MODEL = "black-forest-labs/FLUX.1-schnell"
USER_AGENT = "free-image-skill/1.0"


class ProviderError(Exception):
    pass


def _request(req: urllib.request.Request, timeout: int) -> tuple[bytes, str]:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = resp.headers.get("Content-Type", "")
            data = resp.read()
    except urllib.error.HTTPError as e:
        body = e.read()[:300].decode("utf-8", "replace")
        raise ProviderError(f"HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"network error: {e.reason}") from e
    except TimeoutError as e:
        raise ProviderError("timed out") from e
    if not ctype.startswith("image/"):
        raise ProviderError(f"expected an image, got {ctype or 'no content type'}: {data[:200]!r}")
    return data, ctype


def pollinations(prompt: str, width: int, height: int, seed: int, model: str, timeout: int) -> tuple[bytes, str]:
    query = urllib.parse.urlencode(
        {"width": width, "height": height, "seed": seed, "model": model, "nologo": "true", "enhance": "false"}
    )
    url = POLLINATIONS_URL.format(prompt=urllib.parse.quote(prompt, safe=""), query=query)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return _request(req, timeout)


def huggingface(prompt: str, width: int, height: int, seed: int, model: str, timeout: int) -> tuple[bytes, str]:
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise ProviderError("HF_TOKEN is not set")
    payload = {"inputs": prompt, "parameters": {"width": width, "height": height, "seed": seed}}
    req = urllib.request.Request(
        HF_URL.format(model=model or HF_MODEL),
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "image/png",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    return _request(req, timeout)


PROVIDERS = {"pollinations": pollinations, "hf": huggingface}


def slugify(text: str, limit: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:limit].rstrip("-") or "image"


def generate_one(prompt, width, height, seed, providers, model, timeout, retries):
    errors = []
    for name in providers:
        fn = PROVIDERS[name]
        for attempt in range(retries + 1):
            try:
                data, ctype = fn(prompt, width, height, seed, model if name == "hf" else (model or "flux"), timeout)
                return name, data, ctype
            except ProviderError as e:
                errors.append(f"{name} (try {attempt + 1}): {e}")
                if "HF_TOKEN is not set" in str(e):
                    break
                if attempt < retries:
                    time.sleep(2 ** (attempt + 1))
    raise ProviderError("all providers failed:\n  " + "\n  ".join(errors))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompt", required=True, help="Full image prompt")
    ap.add_argument("--aspect", default="1:1", choices=sorted(ASPECTS), help="Aspect ratio (default 1:1)")
    ap.add_argument("--width", type=int, help="Override width in pixels")
    ap.add_argument("--height", type=int, help="Override height in pixels")
    ap.add_argument("--count", type=int, default=1, help="Number of variants, each with its own seed (max 4)")
    ap.add_argument("--seed", type=int, help="Seed for the first variant (later variants add 1, 2, ...)")
    ap.add_argument("--provider", default="auto", choices=["auto", *PROVIDERS], help="Which free provider to use")
    ap.add_argument("--model", default="", help="Provider model (pollinations: flux, turbo; hf: a model id)")
    ap.add_argument("--out", default="generated-images", help="Output directory")
    ap.add_argument("--name", help="Base filename (default: from prompt)")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--retries", type=int, default=2)
    args = ap.parse_args()

    count = max(1, min(args.count, 4))
    width, height = ASPECTS[args.aspect]
    width, height = args.width or width, args.height or height
    providers = list(PROVIDERS) if args.provider == "auto" else [args.provider]
    base_seed = args.seed if args.seed is not None else random.randint(1, 2**31 - 1)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = args.name or slugify(args.prompt)

    results, failed = [], 0
    for i in range(count):
        seed = base_seed + i
        try:
            provider, data, ctype = generate_one(
                args.prompt, width, height, seed, providers, args.model, args.timeout, args.retries
            )
        except ProviderError as e:
            print(f"[variant {i + 1}] FAILED: {e}", file=sys.stderr)
            failed += 1
            continue
        ext = {"image/png": ".png", "image/webp": ".webp"}.get(ctype.split(";")[0], ".jpg")
        path = out / f"{base}-{stamp}-{i + 1}{ext}"
        path.write_bytes(data)
        meta = {
            "prompt": args.prompt,
            "provider": provider,
            "model": args.model or ("flux" if provider == "pollinations" else HF_MODEL),
            "seed": seed,
            "width": width,
            "height": height,
            "aspect": args.aspect,
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        path.with_suffix(".json").write_text(json.dumps(meta, indent=2) + "\n")
        results.append(str(path))
        print(f"[variant {i + 1}] saved {path} ({provider}, seed {seed}, {len(data) // 1024} KB)")

    print(json.dumps({"saved": results, "failed": failed}))
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
