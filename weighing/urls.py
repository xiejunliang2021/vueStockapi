from django.urls import path
from .views import WeighingRecordViewSet

urlpatterns = [
    path('weighing-records/', WeighingRecordViewSet.as_view(), name='weighing-records'),
]
