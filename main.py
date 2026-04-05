#!/usr/bin/env python3
"""
VII Two — Voice Intelligence Interface v2
Main entry point.

Starts the voice pipeline and optionally the Telegram remote bot.

Usage:
    python main.py                    # Pipeline only
    python main.py --telegram         # Pipeline + Telegram bot
    python main.py --telegram-only    # Telegram bot only (for phone remote)

Environment variables:
    ANTHROPIC_API_KEY       — Claude API key (required)
    VII_TELEGRAM_TOKEN      — Telegram bot token (for remote)
    VII_TELEGRAM_CHAT_ID    — Authorized Telegram chat ID
"""

import argparse
import asyncio
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("vii")


async def run(args):
    """Main async entry point."""
    from core.pipeline.orchestrator import VIIPipelineOrchestrator
    from remote.telegram import VIITelegramBot

    pipeline = None
    telegram_bot = None

    try:
        # Start pipeline (unless telegram-only mode)
        if not args.telegram_only:
            pipeline = VIIPipelineOrchestrator()
            await pipeline.start()
            logger.info("VII Two pipeline running")

        # Start Telegram bot
        if args.telegram or args.telegram_only:
            if not os.environ.get("VII_TELEGRAM_TOKEN"):
                logger.error("VII_TELEGRAM_TOKEN not set")
                sys.exit(1)

            telegram_bot = VIITelegramBot(pipeline=pipeline)
            await telegram_bot.start()
            logger.info("VII Two Telegram bot running")

        # Print status
        print("\n" + "=" * 50)
        print("  VII Two — Voice Intelligence Interface v2")
        print("  Developed by The 747 Lab")
        print("=" * 50)
        if pipeline:
            print("  Pipeline: RUNNING (socket: /tmp/vii-pipeline.sock)")
        if telegram_bot:
            print("  Telegram: RUNNING (remote access enabled)")
        print("=" * 50 + "\n")

        # Keep running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        if telegram_bot:
            await telegram_bot.stop()
        if pipeline:
            await pipeline.stop()
        logger.info("VII Two stopped.")


def main():
    parser = argparse.ArgumentParser(description="VII Two — Voice Intelligence Interface v2")
    parser.add_argument("--telegram", action="store_true", help="Enable Telegram remote bot")
    parser.add_argument("--telegram-only", action="store_true", help="Run Telegram bot only (no local pipeline)")
    args = parser.parse_args()

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
