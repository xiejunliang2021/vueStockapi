from django.urls import path
from .views import WeighingRecordViewSet

urlpatterns = [
    path('weighing-records/', WeighingRecordViewSet.as_view({'get': 'list', 'post': 'create'}), name='weighing-records'),
    path('weighing-records/<int:pk>/', WeighingRecordViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='weighing-record-detail'),
]
