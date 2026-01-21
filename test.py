# -*- coding: UTF-8 -*-
'''
@Project ：vueStockapi 
@File ：test.py
@Author ：Anita_熙烨（路虽远，行则降至！事虽难，做则必成！）
@Date ：2026/1/8 20:00 
@JianShu : 
'''
import logging
import urllib.parse
import re
import base64
import os
import datetime
import asyncio
import pandas as pd
import json
import uuid
import subprocess
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler

# --- 基础配置 ---
BOT_TOKEN = '8436411560:AAENdrBrn25ZjR3KS3WBrqjVkDNtLFaofb0'
STATIC_FILE_PATH = "/var/www/html/subdata/nodes.txt"
IP_POOL_CSV = "/var/www/html/subdata/ip_pool.csv"
NODE_TEMPLATES_CSV = "/var/www/html/subdata/node_templates.csv"
CONFIG_FILE = "/var/www/html/subdata/config.json"
SUB_BASE_URL = "https://subapi.832693.xyz/subdata/nodes.txt"

# Nginx 配置文件路径
NGINX_CONF_PATH = "/etc/nginx/conf.d/subconverter.conf"

# 默认配置
DEFAULT_CONFIG = {
    "latency_limit": 200.0,
    "sub_token": str(uuid.uuid4())
}

# 正则表达式
ADDR_PATTERN = re.compile(
    r'([a-zA-Z0-9][-a-zA-Z0-9]{0,62}(?:\.[a-zA-Z0-9][-a-zA-Z0-9]{0,62})+|[0-9]{1,3}(?:\.[0-9]{1,3}){3})')
MS_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*ms')
IP_ONLY_PATTERN = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'

logging.basicConfig(level=logging.INFO)


# --- 工具函数 ---

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                if "sub_token" not in config:
                    config["sub_token"] = DEFAULT_CONFIG["sub_token"]
                return config
        except:
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG


def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
    except Exception as e:
        print(f"Save Config Error: {e}")


def update_nginx_config(new_token):
    print(f"开始更新 Nginx 配置: {NGINX_CONF_PATH}")
    try:
        if not os.path.exists(NGINX_CONF_PATH):
            return False, f"未找到文件: {NGINX_CONF_PATH}"

        with open(NGINX_CONF_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        pattern = r'\$arg_token\s*!=\s*"[^"]+"'
        if not re.search(pattern, content):
            return False, "Nginx 配置中未匹配到 $arg_token 校验行"

        new_content = re.sub(pattern, f'$arg_token != "{new_token}"', content)
        with open(NGINX_CONF_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)

        subprocess.run(["sudo", "nginx", "-t"], check=True, capture_output=True)
        subprocess.run(["sudo", "nginx", "-s", "reload"], check=True, capture_output=True)
        return True, "Nginx 配置同步成功"
    except Exception as e:
        return False, f"异常: {str(e)}"


def init_csv_files():
    os.makedirs(os.path.dirname(IP_POOL_CSV), exist_ok=True)
    for path, cols in [(IP_POOL_CSV, ['address', 'latency', 'last_checked']),
                       (NODE_TEMPLATES_CSV, ['node_url', 'remarks'])]:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            pd.DataFrame(columns=cols).to_csv(path, index=False)


async def check_tcp_latency(ip, port=443, timeout=2):
    start = asyncio.get_event_loop().time()
    try:
        conn = asyncio.open_connection(ip, port)
        _, writer = await asyncio.wait_for(conn, timeout=timeout)
        writer.close()
        await writer.wait_closed()
        return int((asyncio.get_event_loop().time() - start) * 1000)
    except:
        return None


# --- 核心逻辑 ---

async def generate_subscription():
    config = load_config()
    limit = config.get("latency_limit", 200.0)
    try:
        ips_df = pd.read_csv(IP_POOL_CSV)
        templates_df = pd.read_csv(NODE_TEMPLATES_CSV)
        if ips_df.empty or templates_df.empty: return None, 0

        valid_nodes = []
        tasks = [check_tcp_latency(row['address']) for _, row in ips_df.iterrows()]
        results = await asyncio.gather(*tasks)

        for _, t_row in templates_df.iterrows():
            try:
                parsed = urllib.parse.urlparse(t_row['node_url'])
                user_info, server_info = parsed.netloc.split('@')
                port = server_info.split(':')[1] if ':' in server_info else ""
                tag_base = urllib.parse.unquote(parsed.fragment) if parsed.fragment else "Node"

                for addr, ms in zip(ips_df['address'], results):
                    if ms is None or ms >= limit: continue
                    new_loc = f"{user_info}@{addr}:{port}" if port else f"{user_info}@{addr}"
                    new_node = urllib.parse.urlunparse(
                        parsed._replace(netloc=new_loc, fragment=urllib.parse.quote(f"{tag_base}-{ms}ms")))
                    valid_nodes.append((new_node, ms))
            except:
                continue

        valid_nodes.sort(key=lambda x: x[1])
        final = [x[0] for x in valid_nodes[:100]]
        if final:
            b64 = base64.b64encode("\n".join(final).encode()).decode()
            with open(STATIC_FILE_PATH, "w") as f: f.write(b64)
            return b64, len(final)
    except Exception as e:
        print(f"Generate Error: {e}")
    return None, 0


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理非命令文本消息
    自动识别IP或域名并分类处理
    """
    if not update.message or not update.message.text:
        return
    if update.message.text.startswith('/'):
        return

    text = update.message.text
    line_count = len([l for l in text.split('\n') if l.strip()])

    # 只处理明显的批量导入
    if line_count < 3:
        return

    # 分别统计IP和域名
    ip_count = await process_ip_logic(text)
    domain_count = await process_domain_logic(text)

    if ip_count > 0 or domain_count > 0:
        msg = " 自动识别完成\n"
        if ip_count > 0:
            msg += f"- IP: {ip_count} 个\n"
        if domain_count > 0:
            msg += f"- 域名: {domain_count} 个"
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text(" 未识别到有效地址,请使用命令手动添加")


# --- 新增: 查看域名列表 ---
async def list_domains_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """只显示域名(过滤掉IP)"""
    try:
        df = pd.read_csv(IP_POOL_CSV)
        # 过滤出域名(非纯IP格式)
        domain_df = df[~df['address'].str.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
                                                , na=False)]

        if domain_df.empty:
            await update.message.reply_text(" 暂无域名记录")
            return

        msg = f" 域名列表 (共 {len(domain_df)} 个)\n\n"

        # 显示前20个,按延迟排序
        sorted_df = domain_df.sort_values('latency').head(20)
        for _, row in sorted_df.iterrows():
            latency_str = f"{row['latency']:.0f}ms" if row['latency'] > 0 else "未测"
            msg += f"{latency_str}: {row['address']}\n"

        if len(domain_df) > 20:
            msg += f"\n... 还有 {len(domain_df) - 20} 个域名"

        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f" 读取失败: {str(e)}")


# --- 提取与保存 IP/域名 的通用函数 ---

async def process_ip_logic(text):
    """
    只处理纯IP地址
    域名请使用 process_domain_logic
    """
    new_entries = []
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 严格的IP正则
    ip_pattern = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')

    lines = text.replace('\n', ' ').split()

    for item in lines:
        item = item.strip()
        if not item or "://" in item:
            continue

        # 提取延迟
        latency = 0
        ms_match = MS_PATTERN.search(item)
        if ms_match:
            latency = float(ms_match.group(1))
            item = item.replace(ms_match.group(0), "")

        # 只匹配IP
        ip_match = ip_pattern.search(item)
        if ip_match:
            ip = ip_match.group(0)
            # 验证IP有效性
            parts = ip.split('.')
            if all(0 <= int(p) <= 255 for p in parts):
                new_entries.append({
                    'address': ip,
                    'latency': latency,
                    'last_checked': now
                })

    if new_entries:
        df = pd.read_csv(IP_POOL_CSV)
        updated_df = pd.concat([pd.DataFrame(new_entries), df], ignore_index=True)
        updated_df = updated_df.drop_duplicates(subset=['address'], keep='first')
        updated_df.to_csv(IP_POOL_CSV, index=False)
        return len(new_entries)

    return 0


# --- 指令处理器 ---

async def add_ip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # 改进1: 用换行符连接参数,保持多行结构
        text = "\n".join(context.args).strip()

        if not text:
            await update.message.reply_text("用法: /add_ip [IP或域名]\n支持多个,用空格或换行分隔")
            return

        count = await process_ip_logic(text)
        if count > 0:
            await update.message.reply_text(f" 成功添加 {count} 个地址")
        else:
            await update.message.reply_text(" 未识别到有效地址")
    except Exception as e:
        await update.message.reply_text(f" 添加失败: {str(e)}")


async def clear_ips_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """仅清空纯 IP，保留域名"""
    try:
        df = pd.read_csv(IP_POOL_CSV)
        initial_count = len(df)

        # 改进4: 使用更严格的IP正则
        ip_pattern = r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$'
        df_remaining = df[~df['address'].str.match(ip_pattern, na=False)]

        cleared_count = initial_count - len(df_remaining)
        df_remaining.to_csv(IP_POOL_CSV, index=False)

        await update.message.reply_text(
            f" 清理完成\n"
            f"- 删除IP: {cleared_count} 个\n"
            f"- 保留域名: {len(df_remaining)} 个"
        )
    except Exception as e:
        await update.message.reply_text(f" 清空异常: {str(e)}")


async def get_sub_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    token = config.get("sub_token")
    full_url = f"{SUB_BASE_URL}?token={token}"
    await update.message.reply_text(f"订阅链接:\n{full_url}")


async def refresh_uuid_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_token = str(uuid.uuid4())
    config = load_config()
    config["sub_token"] = new_token
    save_config(config)
    success, message = update_nginx_config(new_token)
    await update.message.reply_text(f"UUID 刷新结果: {message}\n新 Token: {new_token}")


async def add_node_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        parts = update.message.text.split(None, 1)
        if len(parts) < 2:
            await update.message.reply_text("用法: /add_node [链接]")
            return
        url = parts[1].strip()
        now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        df = pd.read_csv(NODE_TEMPLATES_CSV)
        new_row = pd.DataFrame([{'node_url': url, 'remarks': now_time}])
        pd.concat([df, new_row], ignore_index=True).drop_duplicates(subset=['node_url']).to_csv(NODE_TEMPLATES_CSV,
                                                                                                index=False)
        await update.message.reply_text(f"成功: 节点已录入 ({now_time})")
    except Exception as e:
        await update.message.reply_text(f"异常: {str(e)}")


async def process_domain_logic(text):
    """
    专门处理域名的函数
    支持格式:
    - 纯域名: example.com
    - 带延迟: 123.45 ms: example.com
    - 带协议: https://example.com (自动提取域名)
    """
    new_entries = []
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 更强的域名正则 (支持子域名)
    domain_pattern = re.compile(
        r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}'
    )

    # 同时支持换行和空格分割
    lines = text.replace('\n', ' ').split()

    for item in lines:
        item = item.strip()
        if not item:
            continue

        # 提取延迟
        latency = 0
        ms_match = MS_PATTERN.search(item)
        if ms_match:
            latency = float(ms_match.group(1))
            item = item.replace(ms_match.group(0), "")

        # 移除协议前缀
        item = re.sub(r'^https?://', '', item)
        item = re.sub(r'^www\.', '', item)

        # 移除路径和参数
        item = item.split('/')[0].split('?')[0].split('#')[0]

        # 提取域名
        domain_match = domain_pattern.search(item)
        if domain_match:
            domain = domain_match.group(0).lower()  # 统一小写

            # 验证不是纯IP
            if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
                    , domain):
                new_entries.append({
                    'address': domain,
                    'latency': latency,
                    'last_checked': now
                })

    # 保存到CSV
    if new_entries:
        df = pd.read_csv(IP_POOL_CSV)
        updated_df = pd.concat([pd.DataFrame(new_entries), df], ignore_index=True)
        # 去重: 保留最新的记录
        updated_df = updated_df.drop_duplicates(subset=['address'], keep='first')
        updated_df.to_csv(IP_POOL_CSV, index=False)
        return len(new_entries)

    return 0


# --- 新增: 域名上传命令 ---
async def add_domain_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    专门上传域名的命令
    用法: /add_domain example.com www.test.com
    或多行粘贴域名列表
    """
    try:
        text = "\n".join(context.args).strip()

        if not text:
            await update.message.reply_text(
                " 用法: /add_domain [域名]\n\n"
                "支持格式:\n"
                "- example.com\n"
                "- 123ms: www.test.com\n"
                "- https://cdn.example.org\n\n"
                "支持批量粘贴,自动去重"
            )
            return

        count = await process_domain_logic(text)

        if count > 0:
            await update.message.reply_text(
                f" 域名添加成功\n"
                f"新增: {count} 个\n"
                f"已自动去重"
            )
        else:
            await update.message.reply_text(
                " 未识别到有效域名\n\n"
                "请确保格式正确:\n"
                "✓ example.com\n"
                "✓ sub.domain.org\n"
                "✗ 192.168.1.1 (这是IP)"
            )
    except Exception as e:
        logging.error(f"add_domain错误: {e}", exc_info=True)
        await update.message.reply_text(f" 添加失败: {str(e)}")




async def get_commands_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📋 指令列表\n\n"
        "【节点管理】\n"
        " /add_node [URL] - 添加节点模板\n"
        " /nodes - 查看节点模板\n"
        " /del_node [编号] - 删除节点模板\n\n"
        "【地址管理】\n"
        " /add_ip [IP] - 添加IP地址\n"
        " /add_domain [域名] - 添加域名 🆕\n"
        " /ips - 查看IP列表\n"
        " /domains - 查看域名列表 🆕\n"
        " /del_ip [地址] - 删除指定地址\n"
        " /clear_ips - 清空IP(保留域名)\n\n"
        "【订阅管理】\n"
        " /get_sub - 获取订阅链接\n"
        " /refresh_uuid - 刷新Token\n"
        " /refresh - 测速更新\n\n"
        " /get - 显示此列表"
    )
    await update.message.reply_text(help_text)


async def refresh_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("正在更新...")
    _, count = await generate_subscription()
    await update.message.reply_text(f"完成，有效节点数量: {count}")


async def list_ips_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        df = pd.read_csv(IP_POOL_CSV)
        msg = f"总计: {len(df)}\n" + "\n".join(df.head(10)['address'].tolist())
        await update.message.reply_text(msg)
    except:
        await update.message.reply_text("读取失败")


async def list_nodes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        df = pd.read_csv(NODE_TEMPLATES_CSV)
        msg = "节点列表:\n"
        for i, row in df.iterrows():
            msg += f"{i + 1}. {row['remarks']} | {row['node_url'][:30]}...\n"
        await update.message.reply_text(msg)
    except:
        await update.message.reply_text("读取失败")


async def del_node_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        idx = int(context.args[0]) - 1
        df = pd.read_csv(NODE_TEMPLATES_CSV)
        df.drop(df.index[idx]).to_csv(NODE_TEMPLATES_CSV, index=False)
        await update.message.reply_text("删除成功")
    except:
        await update.message.reply_text("编号错误")


async def del_ip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target = " ".join(context.args).strip()
        df = pd.read_csv(IP_POOL_CSV)
        df[df['address'] != target].to_csv(IP_POOL_CSV, index=False)
        await update.message.reply_text(f"已处理: {target}")
    except:
        await update.message.reply_text("操作错误")



if __name__ == '__main__':
    init_csv_files()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # === 帮助和信息命令 ===
    app.add_handler(CommandHandler("get", get_commands_handler))
    app.add_handler(CommandHandler("get_sub", get_sub_handler))

    # === 订阅管理命令 ===
    app.add_handler(CommandHandler("refresh_uuid", refresh_uuid_handler))
    app.add_handler(CommandHandler("refresh", refresh_handler))

    # === 节点模板管理 ===
    app.add_handler(CommandHandler(["add_node", "addnode"], add_node_handler))
    app.add_handler(CommandHandler("nodes", list_nodes_handler))
    app.add_handler(CommandHandler(["del_node", "delnode"], del_node_handler))

    # === IP/域名地址管理 ===
    app.add_handler(CommandHandler("add_ip", add_ip_handler))
    app.add_handler(CommandHandler(["add_domain", "adddomain"], add_domain_handler))  # 🆕 新增域名命令
    app.add_handler(CommandHandler("ips", list_ips_handler))
    app.add_handler(CommandHandler(["domains", "domain"], list_domains_handler))  # 🆕 新增查看域名
    app.add_handler(CommandHandler("del_ip", del_ip_handler))
    app.add_handler(CommandHandler("clear_ips", clear_ips_handler))

    # === 文本消息自动识别 ===
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    # === 启动提示 ===
    print("=" * 50)
    print("Telegram Bot 启动成功!")
    print("=" * 50)
    print(" 可用命令:")
    print("  - /add_ip      : 添加IP地址")
    print("  - /add_domain  : 添加域名 (新功能)")
    print("  - /ips         : 查看IP列表")
    print("  - /domains     : 查看域名列表 (新功能)")
    print("  - /add_node    : 添加节点模板")
    print("  - /get_sub     : 获取订阅链接")
    print("  - /get         : 查看完整命令列表")
    print("=" * 50)
    print(" 等待消息中...")
    print("=" * 50)

    app.run_polling()