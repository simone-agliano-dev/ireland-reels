# Ireland Reels

Turns the videos you post to a Telegram channel into Instagram Reel suggestions about life in Ireland.

Everything here is free: GitHub Actions minutes on a private repo, plus your existing Claude subscription. No API key needed.

1. **Every hour (GitHub Actions):** new videos are downloaded, transcribed, then deleted. Only small metadata is kept.
2. **Every Sunday (a scheduled Claude task in your Claude project):** Claude tags new clips (place, scene, topics, mood, hook score) and turns recent ones into 1 to 3 Reel ideas, with cut order, trim points, hook text, caption and hashtags. It follows [REEL_TASK.md](REEL_TASK.md) and saves the ideas in `suggestions/`.
3. **When new ideas land in `suggestions/` (GitHub Actions):** they're sent to your Telegram **Saved Messages**.

Telegram is the archive: originals stay there. This repo only keeps small metadata per clip (duration, orientation, a few preview frames, a link back to the Telegram message).

## How it works

`.github/workflows/watch-telegram.yml` runs every hour. It runs `scripts/watch.py`, which:

1. finds videos posted to your channel since the last run,
2. downloads each one to a temporary folder,
3. saves `clips/<message_id>/meta.json` and `frames/frame_1..4.jpg` (about 100 KB per clip),
4. transcribes any speech with [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (runs on GitHub's machine, free),
5. deletes the video,
6. commits the new metadata to the repo.

Clips saved before transcription existed are re-downloaded from Telegram once and transcribed automatically.

The weekly Claude task writes `tags` into each `meta.json` and saves `suggestions/<date>.md` and `.json`. It uses tagged clips from the last 30 days that haven't been suggested in the last 14 days. Set `"used_in_reel": true` in a clip's `meta.json` to stop it being suggested again. To change how ideas are written, edit [REEL_TASK.md](REEL_TASK.md).

`.github/workflows/send-suggestions.yml` sends each new idea file to Telegram with `scripts/send_suggestions.py`. To resend one, run that workflow by hand and give it the file name.

## One-time setup (about 10 minutes)

### 1. Get Telegram API keys
1. Go to https://my.telegram.org and log in with your phone number.
2. Open **API development tools** and create an app (any name, e.g. "ireland-reels"; platform "Other").
3. Note the **api_id** and **api_hash**.

### 2. Create a session string (on your own computer)
```bash
pip install telethon
python scripts/login.py
```
Enter the api_id, api_hash, your phone number and the code Telegram sends you. Copy the long string it prints.

> This string can log in as your Telegram account. Only put it in GitHub secrets, never in a file or chat. You can revoke it any time in Telegram: **Settings > Devices**.

### 3. Add GitHub secrets
In the repo: **Settings > Secrets and variables > Actions > New repository secret**. Add:

| Secret | Value |
|---|---|
| `TG_API_ID` | your api_id |
| `TG_API_HASH` | your api_hash |
| `TG_SESSION` | the session string from step 2 |
| `TG_CHANNEL` | your channel's username without `@` (e.g. `simone_ireland_clips`), or its numeric id for a private channel |

### 4. Test it
Go to **Actions > Watch Telegram channel > Run workflow**. After a minute or two, new folders should appear under `clips/`.

## Notes
- **Claude usage**: the weekly task counts toward your Claude plan's normal usage limits, like any other chat. No API credit is used.
- **Privacy**: if your channel has a public username, anyone who finds it can watch the videos. To keep them private, make the channel private in Telegram and set `TG_CHANNEL` to its numeric id.
- **First run** processes up to 15 videos (`MAX_PER_RUN`); older ones are picked up in following runs.
- **GitHub Actions minutes**: a private repo gets 2,000 free minutes a month. An hourly run with nothing new takes under a minute, so this uses roughly 500 to 800 minutes a month.
- GitHub pauses scheduled workflows after 60 days with no activity in the repo. New clips keep it active; if you stop posting for 2 months, re-enable it from the Actions tab.
- To reprocess everything, set `state/last_message_id.json` back to `0`.

## Coming next
- Optional automatic rough cut of a suggested Reel.
