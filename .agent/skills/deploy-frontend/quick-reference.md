# Vue3 前端项目部署快速参考

## 快速命令

### 完整部署流程
```bash
# 1. 进入项目目录
cd /path/to/your/vue3-project

# 2. 构建项目
npm run build

# 3. 执行部署
./deploy.sh
```

### 一键部署（构建 + 部署）
```bash
npm run build && ./deploy.sh
```

## 常用操作

### 回滚到上一版本
```bash
ssh your-server "sudo rm -rf /var/www/dist && sudo mv /var/www/dist.bac /var/www/dist && sudo systemctl reload nginx"
```

### 查看服务器日志
```bash
# Nginx 访问日志
ssh your-server "sudo tail -f /var/log/nginx/access.log"

# Nginx 错误日志
ssh your-server "sudo tail -f /var/log/nginx/error.log"
```

### 检查服务器状态
```bash
# Nginx 状态
ssh your-server "sudo systemctl status nginx"

# 测试 Nginx 配置
ssh your-server "sudo nginx -t"

# 查看磁盘空间
ssh your-server "df -h"
```

### 查看部署文件
```bash
# 列出部署文件
ssh your-server "ls -lah /var/www/dist"

# 检查文件权限
ssh your-server "ls -la /var/www/dist"
```

## 环境变量示例

### .env.production
```env
# API 基础 URL
VITE_API_BASE_URL=https://api.yourdomain.com

# 应用标题
VITE_APP_TITLE=您的应用名称

# 其他环境变量
# VITE_CUSTOM_VAR=value
```

### .env.staging (测试环境)
```env
VITE_API_BASE_URL=https://api-staging.yourdomain.com
VITE_APP_TITLE=您的应用名称 (测试)
```

## vite.config.js 生产配置示例

```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
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
})
```

## SSH 配置示例

### ~/.ssh/config
```
Host your-server-alias
    HostName 168.138.5.55
    User ubuntu
    IdentityFile ~/.ssh/your-key.pem
    ServerAliveInterval 60
```

使用别名连接：
```bash
ssh your-server-alias
```

## 故障排除

### 问题：构建失败
```bash
# 清理缓存
rm -rf node_modules package-lock.json
npm install
npm run build
```

### 问题：上传失败
```bash
# 测试 SSH 连接
ssh your-server "echo 'SSH OK'"

# 检查磁盘空间
ssh your-server "df -h"
```

### 问题：页面 404
```bash
# 检查 Nginx 配置
ssh your-server "sudo cat /etc/nginx/sites-available/your-site"

# 确保有 SPA 路由配置
# try_files $uri $uri/ /index.html;
```

### 问题：API 连接失败
```bash
# 测试 API 连接
curl -I https://api.yourdomain.com/api/health

# 检查后端服务
ssh backend-server "systemctl status your-backend-service"
```

## 部署检查清单

- [ ] 代码已提交（可选）
- [ ] `.env.production` 配置正确
- [ ] 本地构建成功
- [ ] SSH 连接正常
- [ ] 服务器磁盘空间充足
- [ ] 知道如何回滚

部署后：
- [ ] 网站可访问
- [ ] 路由正常
- [ ] API 连接正常
- [ ] 无控制台错误

## 性能优化建议

### 启用 Gzip（Nginx）
```nginx
gzip on;
gzip_vary on;
gzip_min_length 1024;
gzip_types text/plain text/css text/xml text/javascript 
           application/x-javascript application/xml+rss 
           application/javascript application/json;
```

### 静态资源缓存（Nginx）
```nginx
location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff|woff2|ttf|eot)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

### SPA 路由支持（Nginx）
```nginx
location / {
    try_files $uri $uri/ /index.html;
}
```
