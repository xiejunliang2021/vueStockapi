import os
import logging
from decouple import config
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler

# ==========================================
# ⚙️ 配置加载 (基于你的 .env 习惯)
# ==========================================
TOKEN = config('TELEGRAM_BOT_TOKEN_LIANGHUA', default=None)
CHAT_ID = config('TELEGRAM_CHAT_ID', default=None)  # 可用于权限白名单

# Oracle S3 挂载点路径
BASE_STORAGE = "/home/opc/tg_data"
SUB_DIRS = {
    "video": os.path.join(BASE_STORAGE, "videos"),
    "photo": os.path.join(BASE_STORAGE, "photos"),
    "file": os.path.join(BASE_STORAGE, "files")
}

# 设置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)

# 确保挂载点下的子目录存在
for path in SUB_DIRS.values():
    os.makedirs(path, exist_ok=True)

# ==========================================
# 🤖 机器人逻辑
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """响应 /start 命令"""
    await update.message.reply_text(
        "📊 **股票分析系统 - 云端存储助手**\n\n"
        "✅ 已连接到 Oracle S3 (墨尔本)\n"
        "✅ 已识别配置环境\n\n"
        "直接发送视频或照片，我将自动同步到云端存储。",
        parse_mode="Markdown"
    )

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理媒体文件"""
    msg = update.message
    
    # 权限校验：仅处理来自你指定 CHAT_ID 的消息（可选）
    if CHAT_ID and str(msg.chat_id) != str(CHAT_ID):
        logging.warning(f"未经授权的访问: {msg.chat_id}")
        return

    # 1. 识别媒体类型
    if msg.video:
        media = msg.video
        target_dir = SUB_DIRS["video"]
        ext = "mp4"
    elif msg.photo:
        media = msg.photo[-1]  # 获取最高画质
        target_dir = SUB_DIRS["photo"]
        ext = "jpg"
    elif msg.document:
        media = msg.document
        target_dir = SUB_DIRS["file"]
        ext = media.file_name.split('.')[-1] if '.' in media.file_name else "bin"
    else:
        return

    # Telegram Bot API 限制下载超过 20MB 的文件
    limit_20mb = 20 * 1024 * 1024
    if media.file_size > limit_20mb:
        server_ip = "168.138.11.4" # 填入你的公网IP
        await msg.reply_text(
            f" **检测到大文件 ({round(media.file_size/1024/1024, 1)}MB)**\n\n"
            f"此文件已超过 Telegram 20MB 的下载限制。\n"
            f"请通过专用的【直传通道】上传：\n"
            f"http://{server_ip}:8000\n\n"
            f"上传后将自动同步至 Oracle S3。",
            parse_mode="Markdown"
        )
        return

    # 2. 生成文件名和路径
    # 使用 file_unique_id 避免文件名冲突
    file_name = f"{media.file_unique_id}.{ext}"
    save_path = os.path.join(target_dir, file_name)

    # 3. 反馈并下载
    status_msg = await msg.reply_text("🚀 正在抓取并同步至 Oracle S3...")

    try:
        tg_file = await context.bot.get_file(media.file_id)
        # 直接写入挂载点即触发 Rclone 自动上传
        await tg_file.download_to_drive(custom_path=save_path)
        
        await status_msg.edit_text(
            f"✅ **同步成功**\n\n"
            f"📂 目录: `{os.path.basename(target_dir)}` \n"
            f"📄 文件: `{file_name}`",
            parse_mode="Markdown"
        )
        logging.info(f"Successfully synced: {save_path}")
    except Exception as e:
        await status_msg.edit_text(f"❌ 同步失败: {str(e)}")
        logging.error(f"Sync error: {e}")

# ==========================================
# 🚀 启动入口
# ==========================================
if __name__ == '__main__':
    if not TOKEN:
        print("❌ 错误: 未在 .env 中找到 TELEGRAM_BOT_TOKEN_LIANGHUA")
        exit(1)

    app = ApplicationBuilder().token(TOKEN).build()
    
    # 注册处理器
    app.add_handler(CommandHandler('start', start))
    # 过滤视频、照片和文档
    app.add_handler(MessageHandler(
        filters.VIDEO | filters.PHOTO | filters.Document.ALL, 
        handle_media
    ))
    
    print(f"✨ 机器人已启动 (Token: {TOKEN[:8]}...)")
    print(f"📁 挂载点: {BASE_STORAGE}")
    app.run_polling()
