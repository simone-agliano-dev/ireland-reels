"""Send Reel idea files to your Telegram "Saved Messages".

Usage: python scripts/send_suggestions.py suggestions/2026-11-29.md [...]

Run by .github/workflows/send-suggestions.yml whenever new idea files are
pushed to suggestions/. Needs TG_API_ID, TG_API_HASH, TG_SESSION.
"""

import asyncio
import os
import re
import sys
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession

LIMIT = 3900  # Telegram allows 4096 characters per message


def to_telegram(markdown: str) -> list[str]:
    """Telegram shows **bold** and [links](url) but not # headings."""
    text = re.sub(r"^#+ (.*)$", r"**\1**", markdown, flags=re.M)
    # Split before each idea heading so an idea stays in one message when possible.
    sections = [s.strip() for s in re.split(r"(?=^\*\*\d+\. |^\*\*Notes\*\*)", text, flags=re.M) if s.strip()]
    parts, current = [], ""
    for section in sections:
        if current and len(current) + len(section) + 2 > LIMIT:
            parts.append(current)
            current = ""
        current = f"{current}\n\n{section}" if current else section
    if current:
        parts.append(current)
    return [p[i:i + LIMIT] for p in parts for i in range(0, len(p), LIMIT)]


async def main(paths: list[str]) -> int:
    files = [Path(p) for p in paths if p.endswith(".md") and Path(p).exists()]
    if not files:
        print("No idea files to send.")
        return 0
    async with TelegramClient(StringSession(os.environ["TG_SESSION"]),
                              int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"]) as client:
        for f in files:
            for part in to_telegram(f.read_text()):
                await client.send_message("me", part, link_preview=False, parse_mode="md")
            print(f"Sent {f}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
