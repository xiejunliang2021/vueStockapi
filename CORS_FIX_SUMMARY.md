# CORS 跨域问题修复总结

## ✅ 问题已解决

**日期**: 2026-01-28  
**问题**: 前端查询回测结果时遇到 CORS 跨域错误

---

## 🐛 原始错误

### 错误信息

```
Access to XMLHttpRequest at 'http://127.0.0.1:8000/api/backtest/portfolio/results/' 
from origin 'http://localhost:5173' has been blocked by CORS policy: 
No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

### 错误原因

Django 设置中的 CORS 配置过于复杂，存在冗余和冲突的设置：
- `CORS_URLS_REGEX` 限制了 CORS 只对特定 URL 生效
- `CORS_ ALLOW_CREDENTIALS` 重复定义
- 其他不必要的配置项可能导致冲突

---

## 🔧 修复方案

### 修改的文件

`vueStockapi/settings.py` (第 286-347 行)

### 修改内容

**移除的配置项**：
- `CORS_URLS_REGEX` - URL 正则表达式限制
- `CORS_ORIGIN_ALLOW_ALL` - 重复配置
- `CORS_ALLOW_WILDCARDS` - 不必要的配置
- `CORS_ALLOW_NON_STANDARD_CONTENT_TYPE` - 不必要的配置
- `CORS_VARY_HEADER` - 使用默认值即可
- 重复的 `CORS_ALLOW_CREDENTIALS` 定义

**保留的核心配置**：
```python
# CORS 配置
CORS_ALLOW_ALL_ORIGINS = False

# 允许访问的源列表
CORS_ALLOWED_ORIGINS = [
    "https://www.huabenwuxin.com",  # 生产环境
    "http://localhost:5173",        # 开发环境
    "http://127.0.0.1:5173",        # 127.0.0.1
]

# 是否允许携带认证信息
CORS_ALLOW_CREDENTIALS = True

# 允许的 HTTP 方法
CORS_ALLOW_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']

# 允许的请求头
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 
    'content-type', 'dnt', 'origin', 'user-agent',
    'x-csrftoken', 'x-requested-with',
]

# 预检请求缓存时间
CORS_PREFLIGHT_MAX_AGE = 86400  # 24小时

# 暴露的响应头
CORS_EXPOSE_HEADERS = ['content-disposition']
```

---

## ✅ 验证结果

### 测试命令

```bash
uv run python test_cors.py
```

### 测试结果

```
✅ CORS 配置正确！
   允许的源: http://localhost:5173

✅ API 请求成功
   返回数据数量: 10 条

响应头:
  access-control-allow-origin: http://localhost:5173
  access-control-allow-credentials: true
  access-control-expose-headers: content-disposition
```

---

## 📝 重启步骤

修改配置后需要重启 Django 服务器：

```bash
# 停止旧的服务器
pkill -f "manage.py runserver"

# 启动新的服务器
uv run python manage.py runserver 127.0.0.1:8000
```

---

## 🎯 现在可以正常使用

修复后，前端（`http://localhost:5173`）可以正常访问后端 API（`http://127.0.0.1:8000/api/`），不会再出现 CORS 错误。

### 前端请求示例

```javascript
// 在 Vue 3 前端中
const response = await axios.get('http://127.0.0.1:8000/api/backtest/portfolio/results/')
// ✅ 现在可以正常工作
```

---

## 📚 相关文件

- **配置文件**: `vueStockapi/settings.py` (第 286-329 行)
- **测试脚本**: `test_cors.py`
- **中间件配置**: `vueStockapi/settings.py` (第 61 行)

---

## 🔒 生产环境建议

在生产环境部署时，记得：

1. **限制允许的源**：
   ```python
   CORS_ALLOWED_ORIGINS = [
       "https://www.huabenwuxin.com",  # 只允许生产域名
   ]
   ```

2. **使用 HTTPS**：
   确保生产环境使用 HTTPS

3. **检查 ALLOWED_HOSTS**：
   ```python
   ALLOWED_HOSTS = ['www.huabenwuxin.com', '你的服务器IP']
   ```

---

## ✅ 总结

**问题**: CORS 跨域错误  
**原因**: 配置过于复杂，存在冲突  
**解决**: 简化 CORS 配置，移除冗余设置  
**状态**: ✅ 已修复并验证

**现在前端可以正常查询回测结果了！** 🎉
