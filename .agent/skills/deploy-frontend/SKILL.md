---
name: deploy-frontend
description: 部署 Vue3 前端项目到生产服务器。自动执行构建、备份、上传和 Nginx 重启等操作。适用于已配置好服务器环境的前端项目更新部署。
---

# Vue3 前端项目部署 Skill

## 概述

这个 skill 用于将 Vue3 前端项目快速部署到生产服务器。它会自动处理构建、备份、上传和服务重启等所有步骤。

## 适用场景

- ✅ 前端代码有更新，需要部署到生产环境
- ✅ 服务器环境已配置好（Nginx、SSL 证书等）
- ✅ 需要覆盖现有的前端项目
- ✅ 希望自动备份旧版本以便回滚

## 前提条件

### 服务器要求
- 已安装并配置好 Nginx
- 已配置 SSL 证书（HTTPS）
- 已设置 SSH 密钥登录
- 具有 sudo 权限

### 本地要求
- 已配置 `.env.production` 文件
- `vite.config.js` 包含生产构建配置
- 项目可以正常构建（`npm run build`）

## 使用方法

### 快速部署

当用户要求部署前端时，按照以下步骤执行：

#### 步骤 1：确认项目信息

询问或确认以下信息：
- **前端项目路径**（例如：`/Users/xiejunliang/Documents/stock/vue3-project`）
- **服务器 IP** 或 SSH 别名
- **部署目录**（通常是 `/var/www/dist`）
- **生产环境 API 地址**

#### 步骤 2：检查环境配置

1. 检查 `.env.production` 是否存在
   - 如不存在，创建它：
   ```env
   VITE_API_BASE_URL=https://api.yourdomain.com
   VITE_APP_TITLE=应用标题
   ```

2. 检查 `vite.config.js` 是否有生产构建配置
   - 如没有，添加以下配置：
   ```javascript
   build: {
     outDir: 'dist',
     assetsDir: 'assets',
     sourcemap: false,
     minify: 'esbuild',
     rollupOptions: {
       output: {
         manualChunks: {
           'element-plus': ['element-plus'],
           'vue-vendor': ['vue', 'vue-router', 'pinia']
         }
       }
     }
   }
   ```

#### 步骤 3：执行构建

```bash
cd <前端项目路径>
npm run build
```

检查构建是否成功，查看生成的 `dist` 目录。

#### 步骤 4：执行部署

如果项目已有 `deploy.sh` 脚本：
```bash
./deploy.sh
```

如果没有部署脚本，创建一个（使用模板，见下方）或手动执行：
```bash
# 备份
ssh <server> "sudo mv /var/www/dist /var/www/dist.bac"

# 上传
rsync -avz dist/ <server>:/tmp/dist_upload/

# 部署
ssh <server> "sudo mv /tmp/dist_upload/* /var/www/dist/ && sudo systemctl reload nginx"
```

#### 步骤 5：验证部署

1. 访问生产域名，检查页面是否正常显示
2. 测试主要功能和 API 连接
3. 查看浏览器控制台确认无错误

## 部署脚本模板

创建 `deploy.sh` 文件：

```bash
#!/bin/bash

set -e

echo "🚀 开始部署前端项目..."

# 配置变量
SERVER_USER="ubuntu"
SERVER_HOST="YOUR_SERVER_IP"
SERVER_PATH="/var/www"
SSH_ALIAS="YOUR_SSH_ALIAS"

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# 检查 dist 目录
if [ ! -d "dist" ]; then
    echo -e "${RED}❌ dist 目录不存在，请先执行 npm run build${NC}"
    exit 1
fi

# 1. 备份
echo "📦 备份旧版本..."
ssh ${SSH_ALIAS} "
    if [ -d ${SERVER_PATH}/dist ]; then
        sudo rm -rf ${SERVER_PATH}/dist.bac
        sudo mv ${SERVER_PATH}/dist ${SERVER_PATH}/dist.bac
    fi
"

# 2. 上传
echo "📤 上传文件..."
rsync -avz --progress dist/ ${SSH_ALIAS}:/tmp/dist_upload/

# 3. 部署
echo "📁 部署文件..."
ssh ${SSH_ALIAS} "
    sudo mkdir -p ${SERVER_PATH}/dist
    sudo rm -rf ${SERVER_PATH}/dist/*
    sudo mv /tmp/dist_upload/* ${SERVER_PATH}/dist/
    sudo chown -R www-data:www-data ${SERVER_PATH}/dist
    sudo chmod -R 755 ${SERVER_PATH}/dist
    rm -rf /tmp/dist_upload
"

# 4. 重启 Nginx
echo "🔄 重启 Nginx..."
ssh ${SSH_ALIAS} "sudo systemctl reload nginx"

echo -e "${GREEN}✅ 部署完成！${NC}"
echo "🌐 访问: https://your-domain.com"
```

## 快速参考命令

### 构建和部署
```bash
# 完整流程
cd <项目目录>
npm run build && ./deploy.sh

# 仅构建
npm run build

# 仅部署（已有 dist）
./deploy.sh
```

### 回滚操作
```bash
# 快速回滚到上一版本
ssh <server> "sudo rm -rf /var/www/dist && sudo mv /var/www/dist.bac /var/www/dist && sudo systemctl reload nginx"
```

### 查看日志
```bash
# Nginx 访问日志
ssh <server> "sudo tail -f /var/log/nginx/access.log"

# Nginx 错误日志
ssh <server> "sudo tail -f /var/log/nginx/error.log"
```

## 常见问题处理

### 问题 1：构建失败

**检查**：
- Node.js 版本是否正确
- 依赖是否都已安装（`npm install`）
- 是否有语法错误

**解决**：
```bash
# 清理并重新安装依赖
rm -rf node_modules package-lock.json
npm install

# 重新构建
npm run build
```

### 问题 2：上传失败

**检查**：
- SSH 连接是否正常
- 服务器磁盘空间是否充足
- 网络连接是否稳定

**解决**：
```bash
# 测试 SSH 连接
ssh <server> "echo 'SSH 连接正常'"

# 检查磁盘空间
ssh <server> "df -h"

# 手动上传单个文件测试
scp dist/index.html <server>:/tmp/
```

### 问题 3：部署后页面空白

**检查**：
- 浏览器控制台是否有错误
- API 地址是否正确（`.env.production`）
- Nginx 配置是否正确

**解决**：
```bash
# 检查 Nginx 配置
ssh <server> "sudo nginx -t"

# 查看 Nginx 错误日志
ssh <server> "sudo tail -50 /var/log/nginx/error.log"

# 检查文件权限
ssh <server> "ls -la /var/www/dist"
```

### 问题 4：API 请求失败

**检查**：
- 后端服务是否运行
- CORS 配置是否正确
- API 地址是否可访问

**解决**：
```bash
# 测试 API 连接
curl -I https://api.yourdomain.com/api/endpoint

# 检查后端服务状态
ssh <backend-server> "systemctl status <service-name>"
```

## 部署检查清单

在执行部署前，确认：

- [ ] 代码已提交到 Git（可选，但推荐）
- [ ] `.env.production` 配置正确
- [ ] 本地测试通过（`npm run dev`）
- [ ] 构建成功（`npm run build`）
- [ ] 服务器 SSH 连接正常
- [ ] 了解如何回滚（如出现问题）

部署后验证：

- [ ] 网站可以正常访问
- [ ] 所有页面路由正常工作
- [ ] API 连接正常
- [ ] 无控制台错误
- [ ] 移动端显示正常（可选）

## 高级用法

### 多环境部署

如果有多个环境（开发、测试、生产），创建不同的环境变量文件：

```bash
.env.development   # 本地开发
.env.staging       # 测试环境
.env.production    # 生产环境
```

构建时指定环境：
```bash
# 生产环境
npm run build

# 测试环境
npm run build -- --mode staging
```

### 自动化部署（GitHub Actions）

创建 `.github/workflows/deploy.yml`：

```yaml
name: Deploy Frontend

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Node.js
        uses: actions/setup-node@v2
        with:
          node-version: '18'
      
      - name: Install dependencies
        run: npm install
      
      - name: Build
        run: npm run build
      
      - name: Deploy to server
        uses: easingthemes/ssh-deploy@main
        env:
          SSH_PRIVATE_KEY: ${{ secrets.SSH_PRIVATE_KEY }}
          REMOTE_HOST: ${{ secrets.REMOTE_HOST }}
          REMOTE_USER: ${{ secrets.REMOTE_USER }}
          TARGET: /var/www/dist
```

## 总结

这个 skill 提供了完整的前端项目部署流程。主要步骤：

1. **准备**：检查环境配置
2. **构建**：执行 `npm run build`
3. **备份**：备份服务器旧版本
4. **上传**：使用 rsync 上传文件
5. **部署**：移动文件到正确位置
6. **重启**：重启 Nginx 服务
7. **验证**：测试网站功能

遵循这些步骤，可以确保部署过程安全、可靠，并且随时可以回滚。
