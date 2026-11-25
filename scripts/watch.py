"""Pull new videos from a Telegram channel and keep only small metadata.

For every new video in the channel this script:
  1. downloads it to a temporary folder,
  2. reads duration / resolution with ffprobe,
  3. saves a few small preview frames,
  4. writes clips/<message_id>/meta.json with a link back to Telegram,
  5. deletes the video.

The originals stay in Telegram. Nothing large is stored in the repo.

Environment variables (GitHub Actions secrets):
  TG_API_ID, TG_API_HASH  from https://my.telegram.org
  TG_SESSION              string printed by scripts/login.py
  TG_CHANNEL              channel username (e.g. my_ireland_clips) or numeric id
Optional:
  MAX_PER_RUN             max videos to process per run (default 15)
  FRAMES_PER_CLIP         preview frames per clip (default 4)
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from datetime import timezone
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession

ROOT = Path(__file__).resolve().parent.parent
CLIPS_DIR = ROOT / "clips"
STATE_FILE = ROOT / "state" / "last_message_id.json"

MAX_PER_RUN = int(os.environ.get("MAX_PER_RUN", "15"))
FRAMES_PER_CLIP = int(os.environ.get("FRAMES_PER_CLIP", "4"))
FRAME_WIDTH = 480


def load_last_id() -> int:
    if STATE_FILE.exists():
        return int(json.loads(STATE_FILE.read_text())["last_message_id"])
    return 0


def save_last_id(msg_id: int) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"last_message_id": msg_id}, indent=2) + "\n")


def is_video(msg) -> bool:
    if msg.video:
        return True
    doc = msg.document
    return bool(doc and (doc.mime_type or "").startswith("video/"))


def message_link(channel, msg_id: int) -> str:
    username = getattr(channel, "username", None)
    if username:
        return f"https://t.me/{username}/{msg_id}"
    return f"https://t.me/c/{channel.id}/{msg_id}"


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    data = json.loads(out)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
    width, height = video.get("width"), video.get("height")
    # Phones often store portrait video as landscape + a rotation tag.
    rotation = 0
    for side in video.get("side_data_list", []) or []:
        if "rotation" in side:
            rotation = abs(int(side["rotation"]))
    if rotation in (90, 270) and width and height:
        width, height = height, width
    duration = float(data.get("format", {}).get("duration") or 0)
    orientation = None
    if width and height:
        orientation = "vertical" if height > width else "horizontal" if width > height else "square"
    return {
        "duration_s": round(duration, 2),
        "width": width,
        "height": height,
        "orientation": orientation,
        "has_audio": has_audio,
        "size_mb": round(path.stat().st_size / 1_000_000, 1),
    }


def extract_frames(path: Path, duration: float, out_dir: Path) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    names = []
    for i in range(FRAMES_PER_CLIP):
        # Evenly spaced, skipping the very start and end.
        t = duration * (i + 1) / (FRAMES_PER_CLIP + 1) if duration else 0
        name = f"frame_{i + 1}.jpg"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(path),
             "-frames:v", "1", "-vf", f"scale={FRAME_WIDTH}:-2", "-q:v", "5",
             str(out_dir / name)],
            check=True,
        )
        names.append(name)
    return names


async def main() -> int:
    api_id = int(os.environ["TG_API_ID"])
    api_hash = os.environ["TG_API_HASH"]
    session = os.environ["TG_SESSION"]
    channel_ref = os.environ["TG_CHANNEL"].strip()
    if channel_ref.lstrip("-").isdigit():
        channel_ref = int(channel_ref)

    last_id = load_last_id()
    processed = 0

    async with TelegramClient(StringSession(session), api_id, api_hash) as client:
        channel = await client.get_entity(channel_ref)
        print(f"Channel: {getattr(channel, 'title', channel_ref)} | resuming after message {last_id}")

        async for msg in client.iter_messages(channel, min_id=last_id, reverse=True):
            if processed >= MAX_PER_RUN:
                print(f"Reached MAX_PER_RUN={MAX_PER_RUN}; the rest will be picked up next run.")
                break

            if is_video(msg):
                clip_dir = CLIPS_DIR / str(msg.id)
                with tempfile.TemporaryDirectory() as tmp:
                    print(f"Downloading message {msg.id} ...")
                    video_path = Path(await msg.download_media(file=tmp))
                    info = probe(video_path)
                    frames = extract_frames(video_path, info["duration_s"], clip_dir / "frames")
                # Temp folder (and the video) is deleted here.

                meta = {
                    "message_id": msg.id,
                    "telegram_link": message_link(channel, msg.id),
                    "posted_at": msg.date.astimezone(timezone.utc).isoformat(),
                    "caption": msg.message or "",
                    **info,
                    "frames": [f"frames/{f}" for f in frames],
                    # Filled in by the analysis step (transcript + tags).
                    "transcript": None,
                    "tags": None,
                    "used_in_reel": None,
                }
                (clip_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
                processed += 1
                print(f"  saved clips/{msg.id}: {info['duration_s']}s {info['orientation']}")

            # Advance past every message (videos or not) so we never re-scan it.
            last_id = msg.id
            save_last_id(last_id)

    print(f"Done. {processed} new video(s).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
