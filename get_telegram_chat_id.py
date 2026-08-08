import os

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not TOKEN:
    raise SystemExit("Заполни TELEGRAM_BOT_TOKEN в .env перед запуском этого скрипта.")

resp = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates")
data = resp.json()

if not data.get("ok"):
    print("Ошибка:", data)
else:
    results = data.get("result", [])
    if not results:
        print("Пока пусто. Сначала напиши своему боту в Telegram ЛЮБОЕ сообщение (например 'привет'), затем запусти этот скрипт ещё раз.")
    else:
        seen = set()
        for r in results:
            msg = r.get("message", {})
            chat = msg.get("chat", {})
            chat_id = chat.get("id")
            name = chat.get("first_name", "") or chat.get("username", "")
            if chat_id and chat_id not in seen:
                seen.add(chat_id)
                print(f"chat_id: {chat_id}   (это {name})")
