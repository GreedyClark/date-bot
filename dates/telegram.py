import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qsl

import requests
from django.conf import settings

log = logging.getLogger(__name__)

INIT_DATA_MAX_AGE = 60 * 60 * 24


def validate_init_data(init_data: str, bot_token: str, max_age: int = INIT_DATA_MAX_AGE):
    if not init_data or not bot_token:
        return None
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        return None
    try:
        auth_date = int(pairs.get("auth_date", "0"))
        user = json.loads(pairs.get("user", "{}"))
    except ValueError:
        return None
    if time.time() - auth_date > max_age or "id" not in user:
        return None
    return user


def api(method, **payload):
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"
    try:
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        log.warning("Telegram %s не відповів: %s", method, exc)
        return None
    if not data.get("ok"):
        log.warning("Telegram %s повернув помилку: %s", method, data)
    return data


def send_message(chat_id, text, keyboard=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if keyboard:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    return api("sendMessage", **payload)


def app_button(text="Відкрити застосунок"):
    return [[{"text": text, "web_app": {"url": f"{settings.PUBLIC_URL}/app/"}}]]


def invite_link(code):
    return f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={code}"
