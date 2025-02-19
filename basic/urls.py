from django.urls import path
from .views import (
    PolicyDetailsListCreateView, CodeListCreateView, 
    CodeRetrieveUpdateDeleteView, ManualStrategyAnalysisView,
    TradingCalendarListCreateView, TradingCalendarDetailView,
    CheckTradingDayView, StockDailyDataUpdateView,
    StockPatternView
)

urlpatterns = [
    # 策略详情列表和创建
    path('policy-details/', PolicyDetailsListCreateView.as_view(), name='policy-details-list-create'),
    # 获取所有Code并创建新记录
    path('code/', CodeListCreateView.as_view(), name='code-list-create'),  
    # 股票代码详情、更新和删除
    path('code/<str:ts_code>/', CodeRetrieveUpdateDeleteView.as_view(), name='code-detail'), 
    # 手动策略分析
    path('manual-analysis/', ManualStrategyAnalysisView.as_view(), name='manual-analysis'),
    # 交易日历列表和创建
    path('trading-calendar/', TradingCalendarListCreateView.as_view(), name='trading-calendar-list'),
    # 交易日历详情
    path('trading-calendar/<str:date>/', TradingCalendarDetailView.as_view(), name='trading-calendar-detail'),
    # 检查交易日
    path('check-trading-day/', CheckTradingDayView.as_view(), name='check-trading-day'),
    # 更新交易日历
    path('update-trading-calendar/', TradingCalendarListCreateView.as_view(), name='update-trading-calendar'),
    # 更新股票日线数据
    path('update-daily-data/', StockDailyDataUpdateView.as_view(), name='update-daily-data'),
    # 添加新的合并后的路由
    path('stock-pattern/', StockPatternView.as_view(), name='stock-pattern'),
]

