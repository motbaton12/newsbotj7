import os
import json
import time
import logging
from datetime import datetime
import socketio
import requests
from pathlib import Path

# ================== НАСТРОЙКИ ==================
J7_JWT = os.getenv("J7_JWT", "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjQyMDk1LCJ1c2VybmFtZSI6Im5lY2hveHVfNzA0NTY5NDAxMTE4Mjk0MDI2IiwiaXAiOiI0NS4xMS4xOC45MSIsInR5cGUiOiJhY2Nlc3MiLCJzaWQiOiJPMy0xLTRDR0k2T2EwWS00bWlyN1FRIiwiaWF0IjoxNzkzNjg3MDYwLCJleHAiOjE3OTM3MzAyNjB9.A4rEY6VAh5hhXL3etSDcD6Rwmf25gP3VyejdS9uddvHtIXvPPE2q-sCH7yLCMVHX4RafKUtvYle47wQE1N78XA")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "9036508814:AAFdLZqBdvF8CEP7Z0W5HaskCTXheUDkMo8")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL", "@cryptonewsboss")

# Ключевые слова для фильтрации (крипта)
CRYPTO_KEYWORDS = [
    "bitcoin", "btc", "ethereum", "eth", "solana", "sol", "xrp", "ripple",
    "crypto", "cryptocurrency", "blockchain", "defi", "nft", "token",
    "binance", "coinbase", "kraken", "okx", "bybit", "sec", "etf",
    "regulation", "approve", "ban", "listing", "delist", "pump", "dump",
    "market", "price", "rally", "crash", "bull", "bear", "altcoin",
    "memecoin", "dogecoin", "doge", "pepe", "shib", "trump", "elon",
    "saylor", "microstrategy", "grayscale", "blackrock", "fidelity"
]

# Файл для хранения уже отправленных постов
SENT_FILE = Path("sent_posts.json")

# ================== ЛОГИ ==================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("j7bot")

# ================== ФУНКЦИИ ==================
def load_sent():
    if SENT_FILE.exists():
        try:
            return set(json.loads(SENT_FILE.read_text()))
        except:
            return set()
    return set()

def save_sent(sent: set):
    # Храним только последние 5000 id
    data = list(sent)[-5000:]
    SENT_FILE.write_text(json.dumps(data))

def is_crypto_related(text: str) -> bool:
    if not text:
        return False
    text_lower = text.lower()
    return any(kw in text_lower for kw in CRYPTO_KEYWORDS)

def send_to_telegram(text: str, author: str = "", url: str = ""):
    message = f"<b>{author}</b>\n\n{text}"
    if url:
        message += f"\n\n<a href='{url}'>Открыть пост</a>"

    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL,
        "text": message[:4000],
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        r = requests.post(api_url, json=payload, timeout=15)
        if r.status_code == 200:
            log.info(f"✅ Отправлено: {author}")
            return True
        else:
            log.error(f"Telegram error: {r.text}")
            return False
    except Exception as e:
        log.error(f"Telegram exception: {e}")
        return False

# ================== J7 SOCKET ==================
sio = socketio.Client(reconnection=True, reconnection_attempts=0, reconnection_delay=3)

sent_posts = load_sent()

@sio.event
def connect():
    log.info("🔌 Подключился к J7")
    sio.emit("user_connected", J7_JWT)

@sio.event
def connect_error(data):
    log.error(f"Ошибка подключения: {data}")

@sio.event
def disconnect():
    log.warning("Отключился от J7, переподключаюсь...")

@sio.on("auth_error")
def on_auth_error(data):
    log.error(f"Auth error: {data}. JWT вероятно протух.")

@sio.on("initialTweets")
def on_initial(items):
    log.info(f"Получил backlog: {len(items)} постов")

@sio.on("tweet")
@sio.on("tweet_update")
def on_tweet(data):
    try:
        post_id = data.get("id")
        if not post_id or post_id in sent_posts:
            return

        author = data.get("author", {}).get("handle") or data.get("author", {}).get("username") or "unknown"
        text = data.get("text") or ""
        url = data.get("tweetUrl") or f"https://x.com/{author}/status/{post_id}"

        # Фильтр по крипте
        if not is_crypto_related(text) and not is_crypto_related(author):
            return

        # Отправляем
        if send_to_telegram(text, f"@{author}", url):
            sent_posts.add(post_id)
            save_sent(sent_posts)

    except Exception as e:
        log.error(f"Ошибка обработки твита: {e}")

@sio.on("external_message")
def on_external(data):
    # Можно позже добавить обработку других платформ
    pass

def main():
    log.info("🚀 Бот запускается...")
    while True:
        try:
            sio.connect(
                "https://nyc.j7tracker.io",
                transports=["websocket"],
                auth={"token": J7_JWT},
                wait_timeout=20
            )
            sio.wait()
        except Exception as e:
            log.error(f"Ошибка соединения: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
