import re

from botocore.exceptions import ClientError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FieldDefinition, FieldOption, Note, NoteType
from .r2 import R2NotConfigured, upload_image_to_r2
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
    queryset = (
        NoteType.objects.prefetch_related("fields")
        .annotate(notes_count=Count("notes"))
        .order_by("order", "id")
    )
    serializer_class = NoteTypeSerializer


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
        return ctx

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
    """搜索：正文 MySQL 全文检索（ngram）+ 结构化字段值模糊匹配（步骤文字等）。

    查询词拆成布尔模式的 +词查正文；同时用 JSON_SEARCH 在 field_values 里
    做子串匹配，步骤文字、标题、平台等字段值都能搜到。两者都无结果时
    回退到正文模糊匹配（比如单个汉字低于 ngram 最小分词长度）。
    """
    tokens = [t for t in re.split(r"\s+", query) if t]
    tokens = [re.sub(r"[+\-*\"()~<>@]", "", t) for t in tokens]
    tokens = [t for t in tokens if t]
    if not tokens:
        return qs.none()
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


class NoteViewSet(viewsets.ModelViewSet):
    """笔记：增删改查。

    过滤：?type=<类型id> &folder=<文件夹> &tag=<标签> &archived=1 &search=<关键词>
    &field=<字段key> &value=<字段值>（按结构化字段值筛选，多选字段按包含匹配）。
    默认不含归档笔记；?archived=1 只看归档。
    """

    serializer_class = NoteSerializer

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
            qs = qs.filter(tags__contains=[tag])
        field_key = params.get("field")
        field_value = params.get("value")
        if field_key and field_value:
            # 只允许该类型下真实存在的字段 key，避免任意 JSON 路径查询
            fd_qs = FieldDefinition.objects.filter(key=field_key)
            if note_type:
                fd_qs = fd_qs.filter(note_type_id=note_type)
            fd = fd_qs.first()
            if fd is not None:
                if fd.field_type == "multiselect":
                    qs = qs.filter(**{f"field_values__{field_key}__contains": field_value})
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
