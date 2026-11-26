"""Turn recent tagged clips into 1-3 Instagram Reel ideas.

Writes suggestions/<date>.md and .json, and (if the Telegram secrets are set)
sends the ideas to your Telegram "Saved Messages".

Environment:
  ANTHROPIC_API_KEY              required
  TG_API_ID, TG_API_HASH, TG_SESSION   optional, to send the ideas to Telegram
  LOOKBACK_DAYS                  only use clips posted in the last N days (default 30)
  REUSE_AFTER_DAYS               don't re-suggest a clip for N days (default 14)
  MAX_REELS                      at most this many ideas (default 3)
"""

import asyncio
import base64
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIPS_DIR = ROOT / "clips"
OUT_DIR = ROOT / "suggestions"

LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "30"))
REUSE_AFTER_DAYS = int(os.environ.get("REUSE_AFTER_DAYS", "14"))
MAX_REELS = int(os.environ.get("MAX_REELS", "3"))
MAX_CLIPS_SENT = 40

SYSTEM = f"""You are a short-form video editor helping a creator make Instagram Reels about their life living in Ireland.
You get a catalogue of their recent raw phone clips (one preview frame each, plus tags and transcript).
Propose up to {MAX_REELS} Reels that can be cut ONLY from these clips. Rules:
- Reels are vertical, 7-45 seconds. Open with the strongest visual and an on-screen hook that makes people stay.
- Use each clip's real length: start_s/end_s must be inside 0..duration_s. Most cuts are 1-4 seconds; talking-to-camera bits can be longer.
- A clip can appear in only one Reel. Skip clips marked unusable.
- Ground every idea in what the clips actually show; don't invent footage. If a Reel would need one more shot, say so in missing_shots.
- Captions sound like a real person, first person, short, with a question or call to action at the end. 5-12 relevant hashtags.
- If the clips can't make a decent Reel, return fewer ideas (or none) and explain in notes.
Write in English."""

SCHEMA = {
    "type": "object",
    "properties": {
        "reels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Working title, a few words."},
                    "format": {"type": "string", "description": "e.g. day in the life, things that surprised me, POV, list, mini vlog."},
                    "hook_text": {"type": "string", "description": "On-screen text for the first 2 seconds."},
                    "clips": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "message_id": {"type": "integer"},
                                "start_s": {"type": "number"},
                                "end_s": {"type": "number"},
                                "on_screen_text": {"type": "string", "description": "Text overlay for this cut, or ''."},
                                "why": {"type": "string", "description": "Very short: what this cut does in the story."},
                            },
                            "required": ["message_id", "start_s", "end_s", "on_screen_text", "why"],
                            "additionalProperties": False,
                        },
                    },
                    "voiceover": {"type": "string", "description": "Optional voiceover script, or ''."},
                    "music_vibe": {"type": "string", "description": "Kind of trending audio that fits, e.g. 'upbeat acoustic', 'lofi'."},
                    "caption": {"type": "string"},
                    "hashtags": {"type": "array", "items": {"type": "string"}},
                    "missing_shots": {"type": "string", "description": "A shot worth filming to make it better, or ''."},
                },
                "required": ["title", "format", "hook_text", "clips", "voiceover", "music_vibe",
                             "caption", "hashtags", "missing_shots"],
                "additionalProperties": False,
            },
        },
        "notes": {"type": "string", "description": "Short advice for the creator, e.g. what to film next week."},
    },
    "required": ["reels", "notes"],
    "additionalProperties": False,
}


def recently_suggested_ids(now: datetime) -> set[int]:
    ids = set()
    cutoff = now - timedelta(days=REUSE_AFTER_DAYS)
    for f in OUT_DIR.glob("*.json"):
        data = json.loads(f.read_text())
        if datetime.fromisoformat(data["created_at"]) < cutoff:
            continue
        for reel in data["reels"]:
            ids.update(c["message_id"] for c in reel["clips"])
    return ids


def candidate_clips(now: datetime) -> list[tuple[Path, dict]]:
    skip = recently_suggested_ids(now)
    cutoff = now - timedelta(days=LOOKBACK_DAYS)
    out = []
    for meta_file in CLIPS_DIR.glob("*/meta.json"):
        meta = json.loads(meta_file.read_text())
        tags = meta.get("tags") or {}
        if not tags or "error" in tags or not tags.get("usable", True):
            continue
        if meta.get("used_in_reel") or meta["message_id"] in skip:
            continue
        if datetime.fromisoformat(meta["posted_at"]) < cutoff:
            continue
        out.append((meta_file.parent, meta))
    out.sort(key=lambda x: x[1]["message_id"])
    return out[-MAX_CLIPS_SENT:]


def build_content(clips: list[tuple[Path, dict]]) -> list:
    content = []
    for clip_dir, meta in clips:
        frames = meta.get("frames") or []
        if frames:
            middle = frames[len(frames) // 2]
            data = base64.standard_b64encode((clip_dir / middle).read_bytes()).decode()
            content.append({"type": "image",
                            "source": {"type": "base64", "media_type": "image/jpeg", "data": data}})
        info = {
            "message_id": meta["message_id"],
            "posted_at": meta["posted_at"][:10],
            "duration_s": meta["duration_s"],
            "orientation": meta["orientation"],
            "caption": meta.get("caption", ""),
            "tags": meta["tags"],
            "transcript": (meta.get("transcript") or {}).get("segments", []),
        }
        content.append({"type": "text", "text": json.dumps(info, ensure_ascii=False)})
    content.append({"type": "text", "text": "Above: one frame and the details for each clip. Propose the Reels."})
    return content


def to_markdown(result: dict, clips_by_id: dict, date: str) -> str:
    lines = [f"# Reel ideas, {date}", ""]
    if not result["reels"]:
        lines += ["No Reel ideas this time.", ""]
    for n, reel in enumerate(result["reels"], 1):
        total = sum(max(0, c["end_s"] - c["start_s"]) for c in reel["clips"])
        lines += [f"## {n}. {reel['title']}", "",
                  f"{reel['format']}, about {round(total)} s. Music: {reel['music_vibe']}", "",
                  f"**Hook:** {reel['hook_text']}", "", "**Cuts:**"]
        for i, c in enumerate(reel["clips"], 1):
            link = clips_by_id.get(c["message_id"], {}).get("telegram_link", "")
            text = f" | text: \"{c['on_screen_text']}\"" if c["on_screen_text"] else ""
            lines.append(f"{i}. [clip {c['message_id']}]({link}) {c['start_s']:.1f}s to {c['end_s']:.1f}s: {c['why']}{text}")
        lines.append("")
        if reel["voiceover"]:
            lines += [f"**Voiceover:** {reel['voiceover']}", ""]
        lines += ["**Caption:**", "", reel["caption"], "",
                  " ".join(h if h.startswith("#") else f"#{h}" for h in reel["hashtags"]), ""]
        if reel["missing_shots"]:
            lines += [f"**Worth filming:** {reel['missing_shots']}", ""]
    if result["notes"]:
        lines += ["## Notes", "", result["notes"], ""]
    return "\n".join(lines)


def split_for_telegram(markdown: str, limit: int = 3900) -> list[str]:
    """Telegram shows **bold** and [links](url) but not # headings; max ~4096 chars per message."""
    text = re.sub(r"^#+ (.*)$", r"**\1**", markdown, flags=re.M)
    sections = [s.strip() for s in re.split(r"(?=^\*\*\d+\. |^\*\*Notes\*\*)", text, flags=re.M) if s.strip()]
    parts, current = [], ""
    for section in sections:
        if current and len(current) + len(section) + 2 > limit:
            parts.append(current)
            current = ""
        current = f"{current}\n\n{section}" if current else section
    if current:
        parts.append(current)
    return [p[i:i + limit] for p in parts for i in range(0, len(p), limit)]


async def send_to_telegram(markdown: str) -> None:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    async with TelegramClient(StringSession(os.environ["TG_SESSION"]),
                              int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"]) as client:
        for part in split_for_telegram(markdown):
            await client.send_message("me", part, link_preview=False, parse_mode="md")


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set; cannot make suggestions.")
        return 1
    from claude_json import ask_json

    now = datetime.now(timezone.utc)
    clips = candidate_clips(now)
    print(f"{len(clips)} candidate clip(s).")
    if len(clips) < 2:
        print("Not enough new tagged clips for a Reel yet.")
        return 0

    result = ask_json(build_content(clips), SCHEMA, system=SYSTEM, effort="high", max_tokens=16000)

    # Drop cuts that point at unknown clips and clamp trims to the clip length.
    clips_by_id = {m["message_id"]: m for _, m in clips}
    for reel in result["reels"]:
        kept = []
        for c in reel["clips"]:
            meta = clips_by_id.get(c["message_id"])
            if not meta:
                continue
            c["start_s"] = max(0.0, min(c["start_s"], meta["duration_s"]))
            c["end_s"] = max(c["start_s"], min(c["end_s"], meta["duration_s"]))
            kept.append(c)
        reel["clips"] = kept
    result["reels"] = [r for r in result["reels"] if r["clips"]][:MAX_REELS]

    date = now.strftime("%Y-%m-%d")
    OUT_DIR.mkdir(exist_ok=True)
    stem = OUT_DIR / now.strftime("%Y-%m-%d_%H%M")
    stem.with_suffix(".json").write_text(json.dumps(
        {"created_at": now.isoformat(), **result}, indent=2, ensure_ascii=False) + "\n")
    markdown = to_markdown(result, clips_by_id, date)
    stem.with_suffix(".md").write_text(markdown)
    print(f"Wrote {stem.name}.md with {len(result['reels'])} idea(s).")

    if all(os.environ.get(k) for k in ("TG_API_ID", "TG_API_HASH", "TG_SESSION")):
        asyncio.run(send_to_telegram(markdown))
        print("Sent to Telegram Saved Messages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
