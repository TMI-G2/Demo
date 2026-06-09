"""
server.py
----------
Maltego Local Transform Server

Run this once before opening Maltego:
  python server.py

It starts a lightweight HTTP server on localhost:8080.
Maltego sends transform requests to it and receives entity responses back.
All Ollama scoring stays on your machine — nothing is forwarded externally.

Pre-flight checks performed on startup:
  - Apify token set
  - Ollama running and model available
  - All transforms registered correctly
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def preflight_checks() -> bool:
    """Run all startup checks before binding the server port."""
    all_ok = True

    # ── Check Apify token ────────────────────────────────────────────────────
    import config
    if config.APIFY_API_TOKEN == "YOUR_APIFY_TOKEN_HERE":
        log.error(
            "Apify token not set.\n"
            "  Run in PowerShell: $env:APIFY_API_TOKEN = 'apify_api_xxxx'\n"
            "  Then restart: python server.py"
        )
        all_ok = False
    else:
        log.info("✓ Apify token found")

    # ── Check Ollama ─────────────────────────────────────────────────────────
    from utils.ollama_scorer import check_ollama_available
    if check_ollama_available():
        log.info("✓ Ollama running | model: %s", config.OLLAMA_MODEL)
    else:
        log.error(
            "Ollama not available.\n"
            "  1. Check the Ollama icon is in your system tray\n"
            "  2. If not running: start Ollama from the Start menu\n"
            "  3. If model missing: ollama pull %s",
            config.OLLAMA_MODEL,
        )
        all_ok = False

    return all_ok


def main():
    log.info("═" * 55)
    log.info("  Maltego Risk Transform Server")
    log.info("═" * 55)

    if not preflight_checks():
        log.error("Pre-flight checks failed — server not started.")
        sys.exit(1)

    # Import transforms — this triggers @registry.register_transform decorators
    from maltego_trx.registry import register_transform_classes
    import transforms
    register_transform_classes(transforms)

    from maltego_trx import server, registry
    import config

    # List registered transforms
    log.info("Registered transforms:")
    for name in registry.transform_classes:
        log.info("  → %s", name)

    log.info("─" * 55)
    log.info(
        "Server starting on http://%s:%d",
        config.TRANSFORM_SERVER_HOST,
        config.TRANSFORM_SERVER_PORT,
    )
    log.info("Keep this window open while using Maltego.")
    log.info("Press Ctrl+C to stop.")
    log.info("─" * 55)

    server.application.run(
        host=config.TRANSFORM_SERVER_HOST,
        port=config.TRANSFORM_SERVER_PORT,
        debug=False,
    )


if __name__ == "__main__":
    main()
