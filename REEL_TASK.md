# Weekly Reel task (instructions for Claude)

A scheduled Claude task runs these steps once a week. It uses Simone's Claude subscription, so no API key is needed. Edit this file to change how clips are tagged or what the Reel ideas look like.

Simone makes Instagram Reels about their life living in Ireland. Raw clips come from a Telegram channel. The hourly GitHub job saves, for each clip, `clips/<message_id>/meta.json` (length, orientation, caption, speech transcript with timestamps, Telegram link) and 4 evenly spaced preview frames in `clips/<message_id>/frames/`.

## 1. Get the latest clips
Work on `main`. Run `git pull` first.

## 2. Tag clips
For each `clips/*/meta.json` where `tags` is `null`:
- Skip it if `transcript` is `null` and the clip was posted less than 2 days ago (the hourly job hasn't transcribed it yet). Otherwise tag it.
- Look at every frame image, and read the transcript and caption.
- Transcripts come from automatic speech recognition. Treat them with care: short phrases like "Thank you for watching" on a quiet clip are usually recognition errors, and background music can show up as song lyrics. Trust the frames when they disagree.
- Describe only what is visible or said. Don't invent places or events. Keep strings short, in English.
- Set `tags` to exactly this shape:

```json
{
  "summary": "One sentence: what happens in the clip.",
  "place": "Best guess, e.g. 'Dublin city centre street', 'beach', 'home kitchen', or 'unknown'",
  "scene": ["street", "food", "talking_to_camera"],
  "topics": ["weather", "cost of living", "day in the life"],
  "mood": "cosy",
  "talking_to_camera": false,
  "usable": true,
  "quality_notes": "Short note on shakiness, lighting or framing, or ''",
  "hook_score": 3
}
```
`scene` examples: street, nature, coast, home, food, pub, cafe, transport, shopping, work, event, weather, people, talking_to_camera, pet. `topics` are life-in-Ireland themes the clip could illustrate. `usable` is false for blurry, black or accidental clips. `hook_score` is 1 to 5: how well the clip would work as the first 2 seconds of a Reel.

Keep the rest of `meta.json` unchanged (2-space indent, UTF-8).

## 3. Write Reel ideas
Candidate clips: tagged, `usable` true, posted in the last 30 days, `used_in_reel` not true, and not used in any `suggestions/*.json` whose `created_at` is in the last 14 days.

If there are fewer than 2 candidates, skip this step.

Otherwise propose 1 to 3 Reels cut only from the candidates:
- Vertical, 7 to 45 seconds. Open with the strongest visual and an on-screen hook that makes people stay.
- Trim points must fall inside each clip's `duration_s`. Most cuts are 1 to 4 seconds; talking-to-camera parts can be longer. Use transcript timestamps to pick spoken lines.
- Each clip goes in at most one Reel.
- Ground every idea in what the clips actually show. If a Reel needs one more shot, say so under "Worth filming".
- Captions sound like a real person, first person, short, ending with a question or call to action. 5 to 12 relevant hashtags.
- Fewer good ideas beat three weak ones.

Save two files named with today's date (UTC), e.g. `suggestions/2026-11-29.md` and `suggestions/2026-11-29.json`.

`.json` (used to avoid repeating clips):
```json
{
  "created_at": "2026-11-29T10:00:00+00:00",
  "reels": [
    {"title": "...", "clips": [{"message_id": 12, "start_s": 0.5, "end_s": 3.0}]}
  ]
}
```

`.md` (sent to Simone's Telegram, so keep this exact layout: `##` headings, `**bold**` labels, links as `[text](url)`, no tables, no italics):
```markdown
# Reel ideas, 2026-11-29

## 1. Working title

Format (e.g. POV, day in the life, things that surprised me), about 18 s. Music: upbeat acoustic

**Hook:** On-screen text for the first 2 seconds

**Cuts:**
1. [clip 12](https://t.me/...) 0.5s to 3.0s: what this cut does | text: "overlay text"
2. [clip 15](https://t.me/...) 2.0s to 5.5s: what this cut does

**Voiceover:** Optional script (leave this line out if none)

**Caption:**

Caption text here?

#ireland #dublin #lifeinireland

**Worth filming:** Optional shot idea (leave out if none)

## Notes

Short advice, e.g. what to film next week.
```

## 4. Save
Commit with the message `Weekly tags and Reel ideas`, then `git pull --rebase` and `git push` to `main`. Pushing a new `.md` file to `suggestions/` makes GitHub send it to Simone's Telegram Saved Messages.

## 5. Report
Reply with one or two sentences: how many clips you tagged and the titles of the Reel ideas (or why there were none).
