# notes app（vue-notes 后端）

vue-notes 笔记项目的后端，跑在 vueStockapi 里。数据库是事实源头（先 A），以后再加单向导出到 vault，不做双向同步。

## 模型

- **NoteType** 笔记类型：名称、标识、说明。新增类型不用改代码。
- **FieldDefinition** 字段定义：挂在类型下的结构化字段模板。类型：text / textarea / email / datetime / boolean / select；支持必填、默认值、 下拉选项、条件显示（`show_when_key` + `show_when_value`）。
- **Note** 笔记：类型外键 + 结构化字段值 JSON + Markdown 正文 + 文件夹 / 标签 / 置顶 / 归档。

笔记表走 MySQL（`quant` 库），路由见 `weighing/db_router.py`（`notes` 已加入 `route_app_labels`），不要放 Oracle 股票库。

## 接口（全部需要 JWT）

- `GET/POST /api/note-types/`、`GET/PUT/PATCH/DELETE /api/note-types/<id>/`
- `GET/POST /api/note-types/<id>/fields/`、`GET/PUT/PATCH/DELETE /api/note-types/<id>/fields/<field_id>/`
- `GET/POST /api/notes/`、`GET/PUT/PATCH/DELETE /api/notes/<id>/`，过滤：`?type=&folder=&tag=&archived=&search=`
- `POST /api/notes/upload-image/`（multipart，字段名 `file`），返回 `{"url": ...}`

搜索用 MySQL 全文索引（ngram），见 `migrations/0002_fulltext.py`；全文无结果时回退到标题/正文模糊匹配。

必填与格式校验在 serializer 层做（前端表单校验是第二道）。

## 环境变量（后端服务器 .env，不要进仓库）

```
CORS_ALLOWED_ORIGINS=https://notes.huabenwuxin.com
R2_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET=img-disk
R2_PUBLIC_BASE_URL=https://img-r2.832693.xyz/
```

图片存 `notes-image/` 文件夹，与 Obsidian 的 `ob-image/` 分开。

## 依赖

需要 `boto3`（R2 的 S3 API）：`.venv/bin/pip install boto3`。注意 `pyproject.toml` / `uv.lock` 已有未提交改动，boto3 暂只装进 venv，未写进 lockfile；下次整理依赖时记得 `uv add boto3`。

## 常用命令

```bash
.venv/bin/python manage.py makemigrations notes
.venv/bin/python manage.py migrate --database=mysql
.venv/bin/python manage.py seed_note_types   # 创建「网站注册」类型及字段
```

改代码后重载 uWSGI（两个 master 都要 HUP，流量可能落在任一个上；只 HUP master，worker 由 master 重载）：

```bash
kill -HUP $(ps -eo pid,ppid,cmd | awk '/uwsgi --ini/ && $2==1 {print $1}')
```
