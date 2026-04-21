#!/bin/bash
# .agent/skills/sync-all/scripts/sync_frontend.sh

set -e

LOCAL_PATH="/Users/xiejunliang/Documents/stock/vue3-project"
REMOTE_ALIAS="oracle555"
REMOTE_PATH="/var/www/dist"

echo "--- 正在构建前端项目 ---"
cd "$LOCAL_PATH"
npm run build

echo "--- 正在同步前端产物到 $REMOTE_ALIAS ---"
# 先同步到临时目录，避免移动文件时造成短暂的服务不可用
ssh "$REMOTE_ALIAS" "mkdir -p /tmp/dist_upload"
rsync -avz --progress --delete \
    "$LOCAL_PATH/dist/" "${REMOTE_ALIAS}:/tmp/dist_upload/"

echo "📂 正在执行远程部署..."
ssh "$REMOTE_ALIAS" "sudo rm -rf ${REMOTE_PATH}/* && sudo mv /tmp/dist_upload/* ${REMOTE_PATH}/"

echo "✅ 前端同步与部署完成。"
