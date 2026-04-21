#!/bin/bash
# .agent/skills/sync-all/scripts/sync_backend.sh

set -e

LOCAL_PATH="/Users/xiejunliang/Documents/stock/vueStockapi"
REMOTE_ALIAS="oracle114"
REMOTE_PATH="/home/opc/vueStockapi"

echo "--- 正在同步后端代码到 $REMOTE_ALIAS ---"

# 使用 rsync 同步，排除大型和环境特定的文件
rsync -avz --progress \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '.git' \
    --exclude '.agent' \
    --exclude 'logs' \
    --exclude 'uwsgi.sock' \
    --exclude 'uwsgi.pid' \
    --exclude '.env' \
    "$LOCAL_PATH/" "${REMOTE_ALIAS}:${REMOTE_PATH}/"

echo "✅ 文件同步完成。"

echo "🔄 正在远程重启后端服务..."
# 重启 uWSGI 和 Celery 
ssh "$REMOTE_ALIAS" "sudo systemctl restart vuestock-uwsgi vuestock-celery"

echo "✅ 后端服务重启成功。"
