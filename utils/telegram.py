import requests
import logging
from decouple import config

logger = logging.getLogger(__name__)

def send_telegram_message(message, parse_mode="Markdown"):
    """
    发送通知到Telegram机器人
    """
    token = config('TELEGRAM_BOT_TOKEN_LIANGHUA', default=None)
    chat_id = config('TELEGRAM_CHAT_ID', default=None)

    if not token or not chat_id:
        logger.warning("Telegram 通知已跳过：.env 中缺少 TELEGRAM_BOT_TOKEN_LIANGHUA 或 TELEGRAM_CHAT_ID")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        if not data.get("ok"):
            logger.error(f"Telegram 通知发送失败: {data.get('description')}")
            return False
        return True
    except Exception as e:
        logger.error(f"处理 Telegram 通知异常: {e}")
        return False
