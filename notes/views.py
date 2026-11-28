import json
import re

from botocore.exceptions import ClientError
from django.core.cache import cache
from django.db import connections
from django.http import Http404
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    FieldDefinition,
    FieldOption,
    Note,
    NoteType,
    NOTE_TYPES_LIST_CACHE_KEY,
)
from .r2 import R2NotConfigured, upload_image_to_r2

NOTE_TYPES_CACHE_TTL = 600  # 10 分钟缓存（TTL 保底；写路径失效见 models.py 信号）
def _field_options_map():
    """一次取全 FieldOption，按 key 分组（FieldOption 无 LOB 列，单查询约 0.2 秒）。

    供字段定义的 resolved_options 复用，避免每个含 option_group 的字段定义各查一次。
    """
    grouped = {}
    for opt in FieldOption.objects.all().order_by("key", "sort_order", "id"):
        grouped.setdefault(opt.key, []).append(
            {"value": opt.value, "label": opt.label or opt.value}
        )
    return grouped


from .serializers import (
    FieldDefinitionSerializer,
    FieldOptionSerializer,
    NoteSerializer,
    NoteTypeSerializer,
)


class NoteTypeViewSet(viewsets.ModelViewSet):
    """笔记类型：增删改查，列表带字段模板与笔记数。"""

    # 类型和字段是少量参考数据，不分页，前端一次拿全
    pagination_class = None
    serializer_class = NoteTypeSerializer

    def get_queryset(self):
        return (
            NoteType.objects.annotate(notes_count=Count("notes"))
            .order_by("order", "id")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action in ("list", "retrieve"):
            # 修复 ③：下拉选项一次取全走上下文，字段定义不再逐条查 FieldOption。
            context["field_options_map"] = _field_options_map()
        return context

    def _attach_fields(self, note_types):
        # 修复 ⑤a：手动预取字段定义，不用 prefetch_related（它不能带 slice）。
        # Oracle 上 JSON/LOB 列的取回需要 ORDER BY + FETCH FIRST（Top-N 查询随行预取
        # LOB），不带 limit 的预取查询每个 JSON 值多一次 Phoenix 往返（实测 20 行约 9 秒）。
        # limit 1000 远大于实际字段数，不会截断；返回结构与之前完全一致。
        type_ids = [t.id for t in note_types]
        if type_ids:
            fields = list(
                FieldDefinition.objects.filter(note_type_id__in=type_ids)
                .order_by("order", "id")[:1000]
            )
        else:
            fields = []
        by_type = {}
        for fd in fields:
            by_type.setdefault(fd.note_type_id, []).append(fd)
        for nt in note_types:
            nt._prefetched_objects_cache = {"fields": by_type.get(nt.id, [])}

    def list(self, request, *args, **kwargs):
        # 缓存优化：note-types 是低频变更的元数据（类型/字段/选项），
        # 缓存 10 分钟（TTL 保底）；写路径通过 models.py 的 post_save/post_delete
        # 信号失效当前 worker 的缓存。跨 worker 失效依赖 TTL（LocMemCache 进程独立）。
        cached = cache.get(NOTE_TYPES_LIST_CACHE_KEY)
        if cached is not None:
            return Response(cached)
        note_types = list(self.filter_queryset(self.get_queryset()))
        self._attach_fields(note_types)
        serializer = self.get_serializer(note_types, many=True)
        data = serializer.data
        cache.set(NOTE_TYPES_LIST_CACHE_KEY, data, NOTE_TYPES_CACHE_TTL)
        return Response(data)

    def retrieve(self, request, *args, **kwargs):
        note_type = get_object_or_404(
            self.filter_queryset(self.get_queryset()), pk=kwargs["pk"]
        )
        self._attach_fields([note_type])
        self.check_object_permissions(request, note_type)
        serializer = self.get_serializer(note_type)
        return Response(serializer.data)


class FieldDefinitionViewSet(viewsets.ModelViewSet):
    """字段定义：嵌套在类型下，/api/note-types/<id>/fields/。"""

    pagination_class = None
    serializer_class = FieldDefinitionSerializer

    def get_note_type(self):
        return get_object_or_404(NoteType, pk=self.kwargs["note_type_id"])

    def get_queryset(self):
        return FieldDefinition.objects.filter(note_type_id=self.kwargs["note_type_id"])

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["note_type"] = self.get_note_type()
        if self.action in ("list", "retrieve"):
            # 修复 ③：同 NoteTypeViewSet，下拉选项一次取全走上下文。
            ctx["field_options_map"] = _field_options_map()
        return ctx

    def list(self, request, *args, **kwargs):
        # 修复 ⑤a：同 NoteTypeViewSet，字段定义列表加 ORDER BY + FETCH FIRST，
        # 否则每 JSON 值多一次 Phoenix 往返；limit 1000 不截断。
        queryset = self.filter_queryset(self.get_queryset()).order_by("order", "id")[:1000]
        serializer = self.get_serializer(list(queryset), many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save(note_type=self.get_note_type())


class FieldOptionViewSet(viewsets.ModelViewSet):
    """下拉选项：增删改查，?group=<key> 按组过滤。"""

    pagination_class = None
    serializer_class = FieldOptionSerializer

    def get_queryset(self):
        qs = FieldOption.objects.all()
        group = self.request.query_params.get("group")
        if group:
            qs = qs.filter(key=group)
        return qs


def _fulltext_queryset(qs, query):
    """搜索：正文全文检索 + 结构化字段值模糊匹配（步骤文字等）。

    MySQL 分支保持原有行为：正文 MATCH ... AGAINST（ngram）+ JSON_SEARCH
    查 field_values，两者都无结果时回退正文模糊匹配。

    Oracle 分支（_fulltext_queryset_oracle）：正文按词 LIKE（AND，贴近
    MATCH 布尔 +词语义）+ field_values 整段 JSON 序列化后 LIKE（贴近
    JSON_SEARCH 的子串语义，同样大小写敏感）；两者都无结果时回退正文模糊匹配。
    """
    tokens = [t for t in re.split(r"\s+", query) if t]
    tokens = [re.sub(r"[+\-*\"()~<>@]", "", t) for t in tokens]
    tokens = [t for t in tokens if t]
    if not tokens:
        return qs.none()
    if connections[qs.db].vendor == "oracle":
        return _fulltext_queryset_oracle(qs, query, tokens)
    boolean_query = " ".join(f"+{t}" for t in tokens)
    # JSON_SEARCH 的匹配串是 LIKE 模式，先转义用户输入里的通配符
    like = "%" + re.sub(r"([%_\\])", r"\\\1", query) + "%"
    combined = qs.extra(
        where=[
            "(MATCH(`notes_note`.`content`) AGAINST (%s IN BOOLEAN MODE) "
            "OR JSON_SEARCH(`notes_note`.`field_values`, 'one', %s) IS NOT NULL)"
        ],
        params=[boolean_query, like],
    )
    if combined.exists():
        return combined
    return qs.filter(Q(content__icontains=query))


def _fulltext_queryset_oracle(qs, query, tokens):
    """Oracle 分支搜索（见 _fulltext_queryset）。

    - 正文：每词 content__icontains，AND 连接。Django Oracle 后端把
      icontains 编译为 UPPER(字段) LIKEC UPPER(模式)，CLOB/NCLOB 上是否
      可跑待 xszr 实测确认；若报错，改用 DBMS_LOB.INSTR 的 Func 写法。
    - 字段值：JSON_SERIALIZE(field_values RETURNING CLOB) LIKE '%query%'，
      一次覆盖正文字段值、steps 列表文字、平台/范围等普通字段值。
      LIKE 默认大小写敏感，与 MySQL JSON_SEARCH（二进制排序规则）一致。
      注意：序列化文本含 JSON 键名与布尔值字面量，搜 "platform" 或 "true"
      这类词时会额外命中（MySQL JSON_SEARCH 只搜字符串值，不含键名/布尔值）。
    """
    # Oracle 的标识符是大写的：Django 建表为 "NOTES_NOTE"."FIELD_VALUES"，
    # 原生 SQL 里写小写加引号会报 ORA-00942，所以一律用 quote_name 生成。
    qn = connections[qs.db].ops.quote_name
    table = qn(qs.model._meta.db_table)
    field_values_col = qn(qs.model._meta.get_field("field_values").column)
    like = "%" + re.sub(r"([%_\\])", r"\\\1", query) + "%"
    json_where = (
        f"JSON_SERIALIZE({table}.{field_values_col} RETURNING CLOB) "
        f"LIKE %s ESCAPE '\\'"
    )
    content_q = Q()
    for token in tokens:
        content_q &= Q(content__icontains=token)
    combined = qs.filter(content_q) | qs.extra(where=[json_where], params=[like])
    if combined.exists():
        return combined
    return qs.filter(Q(content__icontains=query))


def _oracle_json_path_string(value):
    """把一个值嵌进 Oracle JSON 路径字面量。

    JSON_EXISTS 的路径必须是 SQL 字面量、不能用绑定变量，所以用 json.dumps
    做 JSON 转义（处理 " 与 \），再把 SQL 字面量里的单引号加倍。
    """
    return json.dumps(value, ensure_ascii=False).replace("'", "''")


def _oracle_tags_contains_where(connection, tag):
    """Oracle 上 tags 数组精确包含某标签。

    Django 不支持 Oracle 的 JSON contains（supports_json_field_contains=False），
    等价写法：JSON_EXISTS(tags, '$[*] ? (@ == "tag")')。
    """
    qn = connection.ops.quote_name
    table = qn(Note._meta.db_table)
    tags_col = qn(Note._meta.get_field("tags").column)
    return (
        f"JSON_EXISTS({table}.{tags_col}, "
        f"'$[*] ? (@ == {_oracle_json_path_string(tag)})')"
    )


def _oracle_multiselect_contains_where(connection, field_key, value):
    """Oracle 上多选字段数组精确包含某值。

    等价写法：JSON_EXISTS(field_values, '$."key"[*] ? (@.type() == "string" && @ == "value")')。
    field_key 来自 FieldDefinition.key（SlugField），只能含字母数字与 -_，
    放在 JSON 路径的引号键名里是安全的。
    注意 @.type() == "string" 不可省：Oracle 的 == 是宽松比较，布尔 true、
    数字 5 也会等于字符串 "true"/"5"，而 MySQL 的 JSON contains 是类型敏感的。
    """
    qn = connection.ops.quote_name
    table = qn(Note._meta.db_table)
    field_values_col = qn(Note._meta.get_field("field_values").column)
    return (
        f"JSON_EXISTS({table}.{field_values_col}, "
        f'\'$."{field_key}"[*] ? (@.type() == "string" && @ == {_oracle_json_path_string(value)})\')'
    )


def _oracle_exact_key_where(connection, field_key, value):
    """Oracle 上结构化字段精确匹配（等价于 field_values__{key} = value）。

    Django 4.2 的 ORM 精确查找在 Oracle 上对字符串值恒为假：它编译为
    DBMS_LOB.SUBSTR(COALESCE(JSON_QUERY(...), JSON_VALUE(...))) = JSON_VALUE(...)，
    其中 JSON_QUERY 返回带引号的 "Google"，而等号右边是不带引号的 Google，
    两边永远不等。等价写法：
    JSON_EXISTS(field_values, '$."key" ? (@.type() == "string" && @ == "value")')，
    按 JSON 值语义比较。@.type() == "string" 不可省（同上，Oracle 的 == 是
    宽松比较；MySQL 的 JSON 精确比较是类型敏感的）。
    """
    qn = connection.ops.quote_name
    table = qn(Note._meta.db_table)
    field_values_col = qn(Note._meta.get_field("field_values").column)
    return (
        f"JSON_EXISTS({table}.{field_values_col}, "
        f'\'$."{field_key}" ? (@.type() == "string" && @ == {_oracle_json_path_string(value)})\')'
    )


class NoteViewSet(viewsets.ModelViewSet):
    """笔记：增删改查。

    过滤：?type=<类型id> &folder=<文件夹> &tag=<标签> &archived=1 &search=<关键词>
    &field=<字段key> &value=<字段值>（按结构化字段值筛选，多选字段按包含匹配）。
    默认不含归档笔记；?archived=1 只看归档。
    """

    serializer_class = NoteSerializer

    def retrieve(self, request, *args, **kwargs):
        # 修复 ⑤a：单条详情加 ORDER BY + FETCH FIRST 1，让 Oracle 随行取回 JSON/LOB 列；
        # 不带 limit 的单行查询每个 JSON 值多一次 Phoenix 往返（实测约 0.95 秒）。
        lookup_value = kwargs[self.lookup_url_kwarg or self.lookup_field]
        obj_list = list(
            self.filter_queryset(self.get_queryset())
            .filter(**{self.lookup_field: lookup_value})
            .order_by("-updated_at")[:1]
        )
        if not obj_list:
            raise Http404
        obj = obj_list[0]
        self.check_object_permissions(request, obj)
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

    def get_queryset(self):
        qs = Note.objects.select_related("note_type")
        params = self.request.query_params
        note_type = params.get("type")
        if note_type:
            qs = qs.filter(note_type_id=note_type)
        folder = params.get("folder")
        if folder:
            qs = qs.filter(folder=folder)
        tag = params.get("tag")
        if tag:
            if connections[qs.db].vendor == "oracle":
                qs = qs.extra(where=[_oracle_tags_contains_where(connections[qs.db], tag)])
            else:
                qs = qs.filter(tags__contains=[tag])
        field_key = params.get("field")
        field_value = params.get("value")
        if field_key and field_value:
            # 只允许该类型下真实存在的字段 key，避免任意 JSON 路径查询。
            # 只取 field_type 一列：不碰 FieldDefinition 的 JSON 列（options 等），
            # Oracle 上读 JSON 列曾因驱动已解码而抛 TypeError（现由 models.py 的
            # OracleTolerantJSONField 兜底；这里只取一列则根本不依赖它）。
            fd_qs = FieldDefinition.objects.filter(key=field_key)
            if note_type:
                fd_qs = fd_qs.filter(note_type_id=note_type)
            fd_type = fd_qs.values_list("field_type", flat=True).first()
            if fd_type is not None:
                if fd_type == "multiselect":
                    if connections[qs.db].vendor == "oracle":
                        qs = qs.extra(
                            where=[
                                _oracle_multiselect_contains_where(connections[qs.db], field_key, field_value)
                            ]
                        )
                    else:
                        qs = qs.filter(**{f"field_values__{field_key}__contains": field_value})
                else:
                    if connections[qs.db].vendor == "oracle":
                        qs = qs.extra(
                            where=[
                                _oracle_exact_key_where(
                                    connections[qs.db], field_key, field_value
                                )
                            ]
                        )
                    else:
                        qs = qs.filter(**{f"field_values__{field_key}": field_value})
        archived = params.get("archived")
        if archived is not None:
            qs = qs.filter(is_archived=archived.lower() in ("1", "true"))
        else:
            qs = qs.filter(is_archived=False)
        search = params.get("search", "").strip()
        if search:
            qs = _fulltext_queryset(qs, search)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user.username)


class ImageUploadView(APIView):
    """编辑器图片上传：存 R2 img-disk/notes-image/，返回公网链接。"""

    def post(self, request):
        f = request.FILES.get("file") or request.FILES.get("image")
        if not f:
            return Response({"error": "请选择要上传的图片"}, status=status.HTTP_400_BAD_REQUEST)
        if f.size > 10 * 1024 * 1024:
            return Response({"error": "图片不能超过 10MB"}, status=status.HTTP_400_BAD_REQUEST)
        ext = f.name.rsplit(".", 1)[-1].lower() if "." in f.name else ""
        if ext not in ("jpg", "jpeg", "png", "gif", "webp", "avif"):
            return Response(
                {"error": "只支持 jpg/png/gif/webp/avif 图片"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            url = upload_image_to_r2(f, ext)
        except R2NotConfigured:
            return Response({"error": "图片服务未配置"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ClientError:
            return Response({"error": "图片上传失败，请稍后重试"}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"url": url}, status=status.HTTP_201_CREATED)
