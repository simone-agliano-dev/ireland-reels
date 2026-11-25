"""Run this ONCE on your own computer to log in to Telegram.

It asks for your phone number and the code Telegram sends you, then prints
a long "session string". Paste that string into the GitHub secret TG_SESSION.

    pip install telethon
    python scripts/login.py

Keep the session string private: anyone who has it can use your Telegram
account. You can revoke it any time in Telegram under
Settings > Devices (it shows up as a new device).
"""

from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("API ID (from my.telegram.org): ").strip())
api_hash = input("API hash: ").strip()

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("\nLogged in as:", client.get_me().first_name)
    print("\nYour session string (paste into the TG_SESSION secret):\n")
    print(client.session.save())
