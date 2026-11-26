"""Tag every clip that has a transcript but no tags yet, using Claude.

Claude looks at the clip's preview frames, transcript and caption and returns
a short description plus tags that the weekly Reel suggestions use.

Needs ANTHROPIC_API_KEY. Without it, this script does nothing.
"""

import base64
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIPS_DIR = ROOT / "clips"
MAX_PER_RUN = int(os.environ.get("MAX_TAGS_PER_RUN", "30"))

SYSTEM = (
    "You catalogue short phone videos for a creator who makes Instagram Reels about "
    "their life as someone living in Ireland. For each clip you get evenly spaced "
    "preview frames, the speech transcript (may be empty or in any language) and the "
    "creator's caption. Describe what is actually visible and said; don't invent places "
    "or events. Keep every string short. Write in English."
)

TAG_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "One sentence: what happens in the clip."},
        "place": {"type": "string", "description": "Best guess of where, e.g. 'Dublin city centre street', 'beach', 'home kitchen', or 'unknown'."},
        "scene": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Short labels, e.g. street, nature, coast, home, food, pub, cafe, transport, shopping, work, event, weather, people, talking_to_camera, pet.",
        },
        "topics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Life-in-Ireland themes it could illustrate, e.g. weather, cost of living, Irish food, day in the life, commute, culture shock, nature, nightlife, housing.",
        },
        "mood": {"type": "string", "description": "e.g. cosy, funny, calm, chaotic, rainy, scenic."},
        "talking_to_camera": {"type": "boolean"},
        "usable": {"type": "boolean", "description": "False if blurry, black, accidental or unusable."},
        "quality_notes": {"type": "string", "description": "Very short note on shakiness, lighting, framing, or ''."},
        "hook_score": {"type": "integer", "description": "1-5: how well this clip would work as the first 2 seconds of a Reel."},
    },
    "required": ["summary", "place", "scene", "topics", "mood", "talking_to_camera",
                 "usable", "quality_notes", "hook_score"],
    "additionalProperties": False,
}


def build_content(clip_dir: Path, meta: dict) -> list:
    content = []
    for rel in meta.get("frames", []):
        data = base64.standard_b64encode((clip_dir / rel).read_bytes()).decode()
        content.append({"type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": data}})
    transcript = (meta.get("transcript") or {}).get("text") or "(no speech)"
    content.append({"type": "text", "text": (
        f"Clip length: {meta.get('duration_s')} s, {meta.get('orientation')}.\n"
        f"Frames above are evenly spaced through the clip.\n"
        f"Caption: {meta.get('caption') or '(none)'}\n"
        f"Transcript: {transcript}"
    )})
    return content


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set; skipping tagging.")
        return 0
    from claude_json import ClaudeRefused, ask_json

    tagged = 0
    for meta_file in sorted(CLIPS_DIR.glob("*/meta.json"), key=lambda f: int(f.parent.name)):
        if tagged >= MAX_PER_RUN:
            break
        meta = json.loads(meta_file.read_text())
        # Wait for the transcript so tags see what was said.
        if meta.get("tags") is not None or meta.get("transcript") is None:
            continue
        print(f"Tagging clip {meta['message_id']} ...")
        try:
            meta["tags"] = ask_json(build_content(meta_file.parent, meta), TAG_SCHEMA,
                                    system=SYSTEM, effort="low", max_tokens=4000)
        except ClaudeRefused as e:
            print(f"  declined: {e}")
            meta["tags"] = {"error": "declined"}
        meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
        tagged += 1
    print(f"Tagged {tagged} clip(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
