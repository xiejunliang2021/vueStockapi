---
name: sync-all
description: 自动化同步代码修改到 Git 远程仓库和生产服务器（后端 oracle114，前端 oracle555）。支持单独同步组件或全量同步。
---

# 全量同步 Skill (sync-all)

## 概述
这个技能用于一键同步本地的所有修改。它包含了 Git 提交、后端代码同步、前端构建与部署。

## 适用场景
- ✅ 完成了一个功能点，需要同步到 GitHub。
- ✅ 修复了一个 Bug，需要立即部署到生产环境。
- ✅ 需要同时更新前端和后端的全栈修改。

## 执行流程

当用户说“同步修改”或“部署到服务器”时，请按照以下步骤执行：

### 1. 情况分类
确定用户想要同步的内容：
- **全量同步**：Git + 后端 + 前端
- **仅 Git**：只推送到 GitHub
- **仅后端**：同步到 oracle114 并重启服务
- **仅前端**：在本地构建并同步到 oracle555

### 2. 执行 Git 同步 (推荐)
默认情况下，建议先执行 Git 同步。
```bash
# 后端 Git 同步
./.agent/skills/sync-all/scripts/sync_git.sh /Users/xiejunliang/Documents/stock/vueStockapi "update(backend): automated sync"

# 前端 Git 同步
./.agent/skills/sync-all/scripts/sync_git.sh /Users/xiejunliang/Documents/stock/vue3-project "update(frontend): automated sync"
```

### 3. 执行服务器同步

#### 后端 (oracle114)
```bash
bash ./.agent/skills/sync-all/scripts/sync_backend.sh
```

#### 前端 (oracle555)
```bash
bash ./.agent/skills/sync-all/scripts/sync_frontend.sh
```

## 注意事项
- **权限**：确保本地有执行这些脚本的权限 (`chmod +x`)。
- **环境隔离**：脚本已通过 `--exclude` 自动排除了 `.env` 和虚拟环境，请确保服务器端已存在这些配置。
- **认证**：依赖本地已配置的 SSH 别名 (`oracle114`, `oracle555`)。

## 快速参考
- 同步全部：执行 Git 同步脚本 -> 后端脚本 -> 前端脚本。
- 如果用户没有提供 commit message，请根据 `git diff` 结果生成一个合理的描述。
