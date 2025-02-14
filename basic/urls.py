from django.urls import path
from .views import PolicyDetailsListCreateView,CodeListCreateView, CodeRetrieveUpdateDeleteView

urlpatterns = [
    path('policy-details/', PolicyDetailsListCreateView.as_view(), name='policy-details-list-create'),
    path('code/', CodeListCreateView.as_view(), name='code-list-create'),  # 获取所有Code并创建新记录
    path('code/<str:ts_code>/', CodeRetrieveUpdateDeleteView.as_view(), name='code-detail'),  # 详情、更新、删除
    ]

