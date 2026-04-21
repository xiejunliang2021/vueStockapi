#!/bin/bash
# .agent/skills/sync-all/scripts/sync_git.sh

set -e

REPO_PATH=$1
COMMIT_MSG=${2:-"chore: automatic sync by agent"}

if [ -z "$REPO_PATH" ]; then
    echo "错误: 未提供仓库路径。"
    echo "用法: $0 <repo_path> [commit_message]"
    exit 1
fi

if [ ! -d "$REPO_PATH/.git" ]; then
    echo "错误: $REPO_PATH 不是一个 Git 仓库。"
    exit 1
fi

cd "$REPO_PATH"

echo "--- 正在检查 $REPO_PATH 的 Git 状态 ---"
if [ -z "$(git status --porcelain)" ]; then
    echo "✅ $REPO_PATH 没有需要提交的更改。"
else
    echo "📝 发现更改，正在准备提交..."
    git add .
    git commit -m "$COMMIT_MSG"
    
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    echo "📤 正在推送 $CURRENT_BRANCH 分支到 origin..."
    git push origin "$CURRENT_BRANCH"
    echo "✅ Git 同步完成 ($REPO_PATH)。"
fi
