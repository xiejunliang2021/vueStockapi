from django.urls import path
from .views import (
    PolicyDetailsListCreateView, CodeListCreateView, 
    CodeRetrieveUpdateDeleteView, ManualStrategyAnalysisView,
    TradingCalendarListCreateView, TradingCalendarDetailView,
    CheckTradingDayView
)

urlpatterns = [
    path('policy-details/', PolicyDetailsListCreateView.as_view(), name='policy-details-list-create'),
    path('code/', CodeListCreateView.as_view(), name='code-list-create'),  # 获取所有Code并创建新记录
    path('code/<str:ts_code>/', CodeRetrieveUpdateDeleteView.as_view(), name='code-detail'),  # 详情、更新、删除
    path('manual-analysis/', ManualStrategyAnalysisView.as_view(), name='manual-analysis'),
    path('trading-calendar/', TradingCalendarListCreateView.as_view(), name='trading-calendar-list'),
    path('trading-calendar/<str:date>/', TradingCalendarDetailView.as_view(), name='trading-calendar-detail'),
    path('check-trading-day/', CheckTradingDayView.as_view(), name='check-trading-day'),
    path('update-trading-calendar/', TradingCalendarListCreateView.as_view(), name='update-trading-calendar'),
]

