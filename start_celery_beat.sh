#!/bin/bash
# Celery Beat 启动脚本 (定时任务调度器)

cd "$(dirname "$0")"

echo "=========================================="
echo "⏰ 启动 Celery Beat (定时任务调度器)"
echo "=========================================="

# 检查 Redis 是否运行
echo ""
echo "【步骤 1】检查 Redis 状态..."
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis 正在运行"
else
    echo "❌ Redis 未运行，正在启动..."
    brew services start redis
    sleep 2
    
    if redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis 启动成功"
    else
        echo "❌ Redis 启动失败，请检查安装"
        exit 1
    fi
fi

echo ""
echo "【步骤 2】启动 Celery Beat..."
echo ""

# 启动 Celery Beat
uv run celery -A vueStockapi beat -l info
