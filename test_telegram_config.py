import requests
from decouple import config
import sys

# 该脚本用于测试 .env 文件中的 Telegram 配置是否可用
# 使用方法: .venv/bin/python test_telegram_config.py

def test_telegram():
    print("=" * 50)
    print("🚀 Telegram 机器人配置测试")
    print("=" * 50)

    # 从 .env 读取配置 (使用 python-decouple)
    # 请确保您的 .env 文件中有名为 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID 的项
    TOKEN = config('TELEGRAM_BOT_TOKEN_LIANGHUA', default=None)
    CHAT_ID = config('TELEGRAM_CHAT_ID', default=None)

    if not TOKEN:
        print("❌ 错误: 未在 .env 中找到 TELEGRAM_BOT_TOKEN")
        print("请在 .env 中添加: TELEGRAM_BOT_TOKEN=您的Token")
        sys.exit(1)
    if not CHAT_ID:
        print("❌ 错误: 未在 .env 中找到 TELEGRAM_CHAT_ID")
        print("请在 .env 中添加: TELEGRAM_CHAT_ID=您的ChatID")
        sys.exit(1)

    # 为了安全，只打印 Token 的首尾
    print(f"🔹 识别到 Token: {TOKEN[:8]}...{TOKEN[-5:]}")
    print(f"🔹 识别到 Chat ID: {CHAT_ID}")
    print("-" * 50)

    # 1. 验证机器人身份 (getMe)
    print("正在验证机器人基本信息 (API: getMe)...")
    url_me = f"https://api.telegram.org/bot{TOKEN}/getMe"
    try:
        response = requests.get(url_me, timeout=10)
        data = response.json()
        if data.get("ok"):
            bot_info = data["result"]
            print(f"✅ 机器人验证成功!")
            print(f"   - 显示名称: {bot_info.get('first_name')}")
            print(f"   - 机器人用户名: @{bot_info.get('username')}")
        else:
            print(f"❌ 机器人验证失败: {data.get('description')}")
            print("💡 提示: 请检查您的 TELEGRAM_BOT_TOKEN 是否正确。")
            return
    except Exception as e:
        print(f"❌ 无法连接到 Telegram API: {e}")
        print("💡 提示: 请检查您的网络连接或代理设置。")
        return

    print("-" * 50)

    # 2. 发送测试消息 (sendMessage)
    print(f"正在尝试向 Chat ID {CHAT_ID} 发送测试消息...")
    url_send = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": "📊 **股票分析系统 - 配置验证**\n\n您的 Telegram 机器人机器人通知配置已完成并测试成功！\n\n✅ 身份校验通过\n✅ 消息通道畅通",
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url_send, json=payload, timeout=10)
        data = response.json()
        if data.get("ok"):
            print("✅ 测试消息发送成功！请检查您的 Telegram 手机/电脑客户端。")
        else:
            print(f"❌ 消息发送失败: {data.get('description')}")
            print(f"💡 提示: 1. 请确保您已经主动给机器人发过消息或点过 /start。")
            print(f"      2. 请确保 TELEGRAM_CHAT_ID 是正确的。")
            print(f"      3. 如果是群组，请确保机器人已加入群组且拥有发消息权限。")
    except Exception as e:
        print(f"❌ 发送消息请求时发生错误: {e}")

if __name__ == "__main__":
    test_telegram()
    print("=" * 50)
    print("✨ 测试任务执行完毕")
