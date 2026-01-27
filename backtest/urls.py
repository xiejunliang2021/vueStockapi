from django.urls import path
from .views import PortfolioBacktestResultListView, BatchPortfolioBacktestView, TradeLogListView, PortfolioBacktestDeleteView

app_name = 'backtest'

urlpatterns = [
    # 新的组合回测API
    path('portfolio/run/', BatchPortfolioBacktestView.as_view(), name='run-portfolio-backtest'),
    
    # 新的组合回测结果查询API
    path('portfolio/results/', PortfolioBacktestResultListView.as_view(), name='list-portfolio-results'),
    
    # 获取指定回测的交易日志
    path('portfolio/<int:backtest_id>/trades/', TradeLogListView.as_view(), name='trade-logs'),
    
    # 删除指定的回测记录
    path('portfolio/<int:backtest_id>/delete/', PortfolioBacktestDeleteView.as_view(), name='delete-backtest'),
]

