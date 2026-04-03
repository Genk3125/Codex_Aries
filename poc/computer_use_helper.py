#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont


PLAYWRIGHT_VERSION = "1.53.0"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_url_text(url: str, timeout_sec: int) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    try:
        with urllib.request.urlopen(url, timeout=timeout_sec) as response:  # noqa: S310
            content_type = response.headers.get("Content-Type", "")
            raw = response.read()
            encoding = response.headers.get_content_charset() or "utf-8"
            text = raw.decode(encoding, errors="replace")
        return text, content_type, None
    except urllib.error.URLError as error:
        return None, None, f"URL fetch failed: {error}"
    except Exception as error:  # noqa: BLE001
        return None, None, f"URL fetch failed: {error}"


def extract_text_from_html(html: str, max_chars: int) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    normalized = "\n".join(line for line in lines if line)
    if len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars]


def try_playwright_screenshot(url: str, output_path: Path, timeout_ms: int, full_page: bool) -> Dict[str, Any]:
    cmd: List[str] = [
        "npx",
        "-y",
        f"playwright@{PLAYWRIGHT_VERSION}",
        "screenshot",
        "--browser",
        "chromium",
        "--timeout",
        str(max(1000, timeout_ms)),
        "--wait-for-timeout",
        str(min(max(0, timeout_ms // 2), 30000)),
    ]
    if full_page:
        cmd.append("--full-page")
    cmd.extend([url, str(output_path)])

    process = subprocess.run(cmd, capture_output=True, text=True, check=False, env=os.environ.copy())
    ok = process.returncode == 0 and output_path.exists()
    return {
        "ok": ok,
        "method": "playwright_cli",
        "command": shlex.join(cmd),
        "exit_code": process.returncode,
        "stdout": (process.stdout or "").strip(),
        "stderr": (process.stderr or "").strip(),
        "output_path": str(output_path),
    }


def render_fallback_snapshot(url: str, text: str, output_path: Path, width: int = 1280, height: int = 720) -> Dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (width, height), color=(248, 249, 251))
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.load_default()
    body_font = ImageFont.load_default()

    draw.rectangle([(0, 0), (width, 42)], fill=(34, 40, 49))
    draw.text((12, 12), f"Fallback snapshot: {url}", fill=(255, 255, 255), font=title_font)

    wrapped: List[str] = []
    for line in text.splitlines():
        for chunk in textwrap.wrap(line, width=130):
            wrapped.append(chunk)
    if not wrapped:
        wrapped = ["(no extractable text)"]

    y = 56
    for line in wrapped[:220]:
        draw.text((12, y), line, fill=(20, 20, 20), font=body_font)
        y += 13
        if y > height - 16:
            break

    image.save(output_path)
    return {
        "ok": True,
        "method": "fallback_render",
        "output_path": str(output_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect browser evidence (screenshot/text) as thin computer-use helper")
    parser.add_argument("--url", required=True, help="Target URL")
    parser.add_argument("--operation", choices=["screenshot", "extract_text", "both"], default="both")
    parser.add_argument("--timeout-sec", type=int, default=20)
    parser.add_argument("--timeout-ms", type=int, default=15000, help="browser action timeout for screenshot")
    parser.add_argument("--extract-max-chars", type=int, default=6000)
    parser.add_argument("--output-dir", default="", help="Evidence output directory")
    parser.add_argument("--screenshot-path", default="", help="Optional existing screenshot path to reuse")
    parser.add_argument("--full-page", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else Path.cwd() / ".runtime" / "computer-use"
    output_dir.mkdir(parents=True, exist_ok=True)
    ts_slug = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    screenshot_output = output_dir / f"computer-use-{ts_slug}.png"
    extract_output = output_dir / f"computer-use-{ts_slug}.txt"

    ok = True
    errors: List[Dict[str, str]] = []
    warnings: List[str] = []

    html_text: Optional[str] = None
    content_type: Optional[str] = None

    need_extract = args.operation in {"extract_text", "both"}
    need_screenshot = args.operation in {"screenshot", "both"}

    extract_result: Dict[str, Any] = {
        "executed": False,
        "ok": True,
        "output_path": None,
        "char_count": 0,
        "content_type": None,
    }
    screenshot_result: Dict[str, Any] = {
        "executed": False,
        "ok": True,
        "output_path": None,
        "method": None,
        "command": None,
        "exit_code": None,
    }

    if need_extract or need_screenshot:
        html_text, content_type, fetch_error = fetch_url_text(url=args.url, timeout_sec=max(1, args.timeout_sec))
        if fetch_error:
            errors.append({"code": "FETCH_FAILED", "message": fetch_error})
            ok = False

    if need_extract and html_text is not None:
        extracted = extract_text_from_html(html=html_text, max_chars=max(200, args.extract_max_chars))
        extract_output.write_text(extracted + "\n", encoding="utf-8")
        extract_result = {
            "executed": True,
            "ok": True,
            "output_path": str(extract_output),
            "char_count": len(extracted),
            "content_type": content_type,
            "preview": extracted[:300],
        }
    elif need_extract:
        extract_result = {
            "executed": True,
            "ok": False,
            "output_path": None,
            "char_count": 0,
            "content_type": content_type,
        }

    if need_screenshot:
        if args.screenshot_path:
            supplied = Path(args.screenshot_path)
            if supplied.exists():
                screenshot_result = {
                    "executed": True,
                    "ok": True,
                    "output_path": str(supplied),
                    "method": "provided_path",
                    "command": None,
                    "exit_code": 0,
                }
            else:
                ok = False
                errors.append({"code": "SCREENSHOT_PATH_NOT_FOUND", "message": f"screenshot path not found: {supplied}"})
                screenshot_result = {
                    "executed": True,
                    "ok": False,
                    "output_path": None,
                    "method": "provided_path",
                    "command": None,
                    "exit_code": None,
                }
        else:
            cli_try = try_playwright_screenshot(
                url=args.url,
                output_path=screenshot_output,
                timeout_ms=max(1000, args.timeout_ms),
                full_page=args.full_page,
            )
            if cli_try["ok"]:
                screenshot_result = {
                    "executed": True,
                    "ok": True,
                    "output_path": cli_try["output_path"],
                    "method": cli_try["method"],
                    "command": cli_try["command"],
                    "exit_code": cli_try["exit_code"],
                }
            else:
                warnings.append("playwright CLI screenshot failed; fallback rendered snapshot was used")
                fallback_text = ""
                if html_text is not None:
                    fallback_text = extract_text_from_html(html_text, max_chars=12000)
                fallback = render_fallback_snapshot(args.url, fallback_text, screenshot_output)
                screenshot_result = {
                    "executed": True,
                    "ok": fallback["ok"],
                    "output_path": fallback["output_path"],
                    "method": fallback["method"],
                    "command": cli_try["command"],
                    "exit_code": cli_try["exit_code"],
                    "playwright_stderr": cli_try["stderr"],
                }

    if need_extract and not extract_result.get("ok"):
        ok = False
    if need_screenshot and not screenshot_result.get("ok"):
        ok = False

    output: Dict[str, Any] = {
        "ts": utc_now_iso(),
        "helper": "computer_use_helper",
        "mode": "strict" if args.strict else "fail-open",
        "ok": ok,
        "input": {
            "url": args.url,
            "operation": args.operation,
            "timeout_sec": args.timeout_sec,
            "timeout_ms": args.timeout_ms,
            "extract_max_chars": args.extract_max_chars,
            "output_dir": str(output_dir),
        },
        "evidence": {
            "screenshot": screenshot_result,
            "extract_text": extract_result,
        },
        "errors": errors,
        "warnings": warnings,
        "note": "Evidence collector only. Final PASS/PARTIAL/FAIL judgment remains with verifier.",
    }

    text = json.dumps(output, ensure_ascii=False, indent=2)
    print(text)

    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")

    if args.strict and not ok:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
