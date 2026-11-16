from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FieldDefinitionViewSet, ImageUploadView, NoteTypeViewSet, NoteViewSet

router = DefaultRouter()
router.register(r"note-types", NoteTypeViewSet, basename="note-type")
router.register(r"notes", NoteViewSet, basename="note")

field_list = FieldDefinitionViewSet.as_view({"get": "list", "post": "create"})
field_detail = FieldDefinitionViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)

urlpatterns = [
    # 注意：upload-image 必须在 router 之前，否则会被 notes/<pk>/ 吞掉
    path("notes/upload-image/", ImageUploadView.as_view(), name="note-upload-image"),
    path(
        "note-types/<int:note_type_id>/fields/",
        field_list,
        name="note-type-fields",
    ),
    path(
        "note-types/<int:note_type_id>/fields/<int:pk>/",
        field_detail,
        name="note-type-field-detail",
    ),
    path("", include(router.urls)),
]
