"""Safe configuration diagnostic. Never prints the API key.

    python scripts/check_config.py               # offline: is a key configured, where from, settings
    python scripts/check_config.py --verify      # + live: key accepted? model available? (lists models,
                                                 #   no generation request)
    python scripts/check_config.py --generate    # + one tiny request WITH a system instruction
                                                 #   (proves the v1beta API version works)
    python scripts/check_config.py --image data/front.jpg   # + analyse one photo (1 vision call, no cache)
    python scripts/check_config.py --list-models # print the models this key can use

"Configured" only means a key is visible to this process. "Verified" means Google accepted it.
Exit code: 0 = OK for what was requested, 1 = problem found.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import analyse, settings  # noqa: E402

try:                                   # Windows consoles default to cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):   # pragma: no cover
    pass


def _row(label: str, value) -> None:
    print(f"  {label:<20}: {value}")


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _sdk_info() -> str:
    try:
        from google.genai import _api_client, version
        return f"google-genai {version.__version__} (its own default for the Developer API: " \
               f"'{getattr(_api_client, 'GOOGLE_AI_API_DEFAULT_VERSION', '?')}')"
    except Exception as exc:                       # noqa: BLE001
        return f"google-genai not importable: {exc}"


def _embedding_cached(model: str) -> str:
    try:
        from huggingface_hub import try_to_load_from_cache
        hit = try_to_load_from_cache(model, "config.json")
        return "yes (local Hugging Face cache)" if isinstance(hit, str) else \
            "no - first app start / index build downloads it (~90 MB, needs internet once)"
    except Exception as exc:                       # noqa: BLE001
        return f"unknown ({exc})"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verify", action="store_true", help="contact Google: key accepted + model available")
    ap.add_argument("--generate", action="store_true", help="also send one tiny system-instruction request")
    ap.add_argument("--image", help="also analyse one photo (fresh call, bypasses the cache)")
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--json", action="store_true", help="machine-readable output (still no key)")
    args = ap.parse_args()

    status = settings.api_key_status()
    cfg = settings.describe()
    hints = settings.diagnostics()
    report = {"config": cfg, "key": {k: v for k, v in status.as_dict().items()}, "hints": hints}
    problem = False

    if not args.json:
        print("AutoInspect configuration check")
        _row("Project root", cfg["project_root"])
        _row(".env file", f"{cfg['env_file']} ({'exists' if status.env_file_exists else 'MISSING'})")
        _row(".env status", cfg["env_file_status"])
        _row("Gemini key", ("CONFIGURED" if status.configured else "NOT CONFIGURED")
             + (f" via {status.variable} from the {status.source} (value hidden)" if status.configured else ""))
        if status.problem:
            _row("  note", status.problem)
        _row("Gemini model", f"{cfg['gemini_model']} ({cfg['gemini_model_source']})")
        _row("API version", f"{cfg['gemini_api_version']} (set explicitly on the client)")
        _row("SDK", _sdk_info())
        _row("Timeout / retries", f"{cfg['gemini_timeout_s']} s / {cfg['gemini_max_retries']}")
        _row("Embedding model", f"{cfg['embedding_model']} - cached: {_embedding_cached(cfg['embedding_model'])}")
        _row("Pricing index dir", cfg["index_dir"])
        _row("Vision cache dir", cfg["vision_cache_dir"])
        busy = [p for p in (8501, 8502, 8503) if _port_in_use(p)]
        if busy:
            _row("Running servers", f"something is listening on port(s) {busy}. A Streamlit server keeps the "
                 "environment it was started with: if it started before the key was set, stop it (Ctrl+C) "
                 "and start it again, or press 'Reload configuration' in the app.")
        for h in hints:
            print(f"  HINT: {h}")

    if not status.configured:
        problem = True

    if args.verify or args.generate or args.list_models or args.image:
        if not status.configured:
            msg = "Cannot verify: no key configured."
            report["verify"] = {"ok": False, "detail": msg}
            if not args.json:
                print(f"\nAPI connection: NOT VERIFIED - {msg}")
        elif args.list_models:
            try:
                names = sorted(m.name.removeprefix("models/") for m in analyse._get_client().models.list())
                print("\n".join(names))
            except Exception as exc:                # noqa: BLE001
                print(f"ERROR listing models: {analyse._redact(exc)}")
                problem = True
        else:
            res = analyse.verify_connection(generate=args.generate)
            report["verify"] = res
            problem = problem or not res["ok"]
            if not args.json:
                print(f"\nAPI connection: {'VERIFIED' if res['ok'] else 'FAILED'} "
                      f"(model {res['model']}, api {res['api_version']}, stage {res['stage']})")
                print(f"  {res['detail']}")
            if res["ok"] and args.image:
                from src.intake import load_image
                img = load_image(args.image)
                print(f"Image OK: {img.name} {img.width}x{img.height}, sharpness {img.blur_score:.0f}, "
                      f"id {img.image_id}")
                try:
                    out = analyse.analyse_image(img.jpeg_bytes, use_cache=False)
                except analyse.AnalysisError as exc:
                    print(f"Image analysis FAILED: {exc}")
                    return 1
                print(f"Image analysis OK ({analyse.result_provenance(out).get('source')}): "
                      f"view={out.view}, {len(out.damages)} finding(s), is_vehicle={out.is_vehicle}")
                print(json.dumps(out.model_dump(), indent=2)[:3000])

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    elif not (args.verify or args.generate or args.image or args.list_models):
        print("\nKey configured does NOT mean it works. Run with --verify to contact Google "
              "(no generation request), or --generate to also prove system instructions are accepted.")
    return 1 if problem else 0


if __name__ == "__main__":
    sys.exit(main())
