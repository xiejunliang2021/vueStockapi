# 服务器配置信息

## 前端服务器
- **IP**: 168.138.5.55
- **SSH**: `ssh oracle555`
- **域名**: https://www.huabenwuxin.com
- **部署路径**: `/var/www/dist`

## 后端服务器
- **IP**: 168.138.11.4
- **SSH**: `ssh oracle114`
- **API 域名**: https://api.huabenwuxin.com
- **项目路径**: /home/opc/vueStockapi
- **重启命令**: `sudo systemctl restart vuestock-uwsgi vuestock-celery`
- **包管理器**: uv

## 服务管理

### 重启后端服务
```bash
ssh oracle114
sudo systemctl restart vuestock-uwsgi vuestock-celery
```

### 查看服务状态
```bash
ssh oracle114
sudo systemctl status vuestock-uwsgi
sudo systemctl status vuestock-celery
```

### 部署后端代码
```bash
ssh oracle114
cd /home/opc/vueStockapi  # 待确认实际路径
git pull origin main
sudo systemctl restart vuestock-uwsgi vuestock-celery
```

### 部署前端代码
```bash
# 本地构建
cd /Users/xiejunliang/Documents/stock/vue3-project
npm run build
./deploy.sh
```
