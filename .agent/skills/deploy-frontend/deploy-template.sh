#!/bin/bash

# Vue3 前端项目部署脚本模板
# 复制此文件到您的前端项目根目录并根据实际情况修改配置

set -e  # 遇到错误立即退出

echo "🚀 开始部署 Vue3 前端项目到生产服务器..."
echo "================================================"

# ==================== 配置区域 ====================
# 请根据您的实际环境修改以下配置

# 服务器配置
SERVER_USER="ubuntu"                    # SSH 登录用户名
SERVER_HOST="168.138.5.55"             # 服务器 IP 地址
SERVER_PATH="/var/www"                  # 服务器部署路径
BACKUP_DIR="/var/www/dist.bac"         # 备份目录
SSH_ALIAS="oracle555"                   # SSH 配置别名（如果有）

# 项目配置
DOMAIN="www.huabenwuxin.com"           # 您的域名
BUILD_DIR="dist"                        # 构建输出目录

# ==================== 脚本开始 ====================

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 显示配置信息
echo -e "${BLUE}配置信息:${NC}"
echo "  服务器: ${SERVER_HOST}"
echo "  部署路径: ${SERVER_PATH}/${BUILD_DIR}"
echo "  域名: https://${DOMAIN}"
echo ""

# 检查 dist 目录是否存在
if [ ! -d "${BUILD_DIR}" ]; then
    echo -e "${RED}❌ ${BUILD_DIR} 目录不存在，请先执行 npm run build${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} 找到 ${BUILD_DIR} 目录"

# 询问确认
read -p "是否继续部署? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "部署已取消"
    exit 0
fi

# 1. 在服务器上备份旧版本
echo ""
echo "📦 步骤 1/4: 备份服务器上的旧版本..."
ssh ${SSH_ALIAS} "
    if [ -d ${SERVER_PATH}/${BUILD_DIR} ]; then
        sudo rm -rf ${BACKUP_DIR}
        sudo mv ${SERVER_PATH}/${BUILD_DIR} ${BACKUP_DIR}
        echo '旧版本已备份到 ${BACKUP_DIR}'
    else
        echo '没有找到旧版本，跳过备份'
    fi
"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} 备份完成"
else
    echo -e "${RED}❌ 备份失败${NC}"
    exit 1
fi

# 2. 上传新版本到服务器
echo ""
echo "📤 步骤 2/4: 上传文件到服务器..."
rsync -avz --progress \
    --exclude='.*' \
    --exclude='node_modules' \
    ${BUILD_DIR}/ ${SSH_ALIAS}:/tmp/dist_upload/

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} 文件上传完成"
else
    echo -e "${RED}❌ 上传失败${NC}"
    exit 1
fi

# 3. 移动文件到正确位置
echo ""
echo "📁 步骤 3/4: 部署文件到 ${SERVER_PATH}/${BUILD_DIR}..."
ssh ${SSH_ALIAS} "
    sudo mkdir -p ${SERVER_PATH}/${BUILD_DIR}
    sudo rm -rf ${SERVER_PATH}/${BUILD_DIR}/*
    sudo mv /tmp/dist_upload/* ${SERVER_PATH}/${BUILD_DIR}/
    sudo chown -R www-data:www-data ${SERVER_PATH}/${BUILD_DIR}
    sudo chmod -R 755 ${SERVER_PATH}/${BUILD_DIR}
    rm -rf /tmp/dist_upload
"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} 文件部署完成"
else
    echo -e "${RED}❌ 部署失败，正在回滚...${NC}"
    # 回滚
    ssh ${SSH_ALIAS} "
        if [ -d ${BACKUP_DIR} ]; then
            sudo rm -rf ${SERVER_PATH}/${BUILD_DIR}
            sudo mv ${BACKUP_DIR} ${SERVER_PATH}/${BUILD_DIR}
            echo '已回滚到旧版本'
        fi
    "
    exit 1
fi

# 4. 重启 Nginx
echo ""
echo "🔄 步骤 4/4: 重启 Nginx..."
ssh ${SSH_ALIAS} "sudo systemctl reload nginx"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Nginx 已重启"
else
    echo -e "${YELLOW}⚠${NC} Nginx 重启可能失败，请手动检查"
fi

# 显示完成信息
echo ""
echo "================================================"
echo -e "${GREEN}✅ 部署完成！${NC}"
echo ""
echo "📍 访问地址:"
echo "   🌐 https://${DOMAIN}"
echo ""
echo "📝 备份位置:"
echo "   📦 ${BACKUP_DIR}"
echo ""
echo "💡 如需回滚，执行:"
echo "   ${YELLOW}ssh ${SSH_ALIAS} \"sudo rm -rf ${SERVER_PATH}/${BUILD_DIR} && sudo mv ${BACKUP_DIR} ${SERVER_PATH}/${BUILD_DIR} && sudo systemctl reload nginx\"${NC}"
echo ""
echo "🧪 建议操作:"
echo "   1. 访问网站测试功能"
echo "   2. 检查浏览器控制台无错误"
echo "   3. 测试 API 连接"
echo ""
