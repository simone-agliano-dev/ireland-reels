"""Small helper: ask Claude for JSON that matches a schema."""

import json
import os

import anthropic

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")

_client = None


class ClaudeRefused(Exception):
    pass


def ask_json(content: list, schema: dict, *, system: str, effort: str = "medium",
             max_tokens: int = 16000) -> dict:
    """Send one user turn and return the parsed JSON object."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    response = _client.beta.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": content}],
        output_config={
            "effort": effort,
            "format": {"type": "json_schema", "schema": schema},
        },
        # If a safety classifier declines, retry on a suitable fallback model.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        raise ClaudeRefused(getattr(response.stop_details, "explanation", None) or "refused")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Claude's answer was cut off (max_tokens)")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)
