# Ireland Reels

Turns the videos you post to a Telegram channel into Instagram Reel suggestions about life in Ireland.

Telegram is the archive: originals stay there. This repo only keeps small metadata per clip (duration, orientation, a few preview frames, a link back to the Telegram message).

## How it works

`.github/workflows/watch-telegram.yml` runs every hour. It runs `scripts/watch.py`, which:

1. finds videos posted to your channel since the last run,
2. downloads each one to a temporary folder,
3. saves `clips/<message_id>/meta.json` and `frames/frame_1..4.jpg` (about 100 KB per clip),
4. deletes the video,
5. commits the new metadata to the repo.

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
- **First run** processes up to 15 videos (`MAX_PER_RUN`); older ones are picked up in following runs.
- **GitHub Actions minutes**: a private repo gets 2,000 free minutes a month. An hourly run with nothing new takes under a minute, so this uses roughly 500 to 800 minutes a month.
- GitHub pauses scheduled workflows after 60 days with no activity in the repo. New clips keep it active; if you stop posting for 2 months, re-enable it from the Actions tab.
- To reprocess everything, set `state/last_message_id.json` back to `0`.

## Coming next
- Transcripts of speech in each clip and content tags (place, food, weather, talking to camera).
- Weekly Reel suggestions: clip order, trim points, hook, caption, hashtags.
