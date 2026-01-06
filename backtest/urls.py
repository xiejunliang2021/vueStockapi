from django.urls import path
from .views import PortfolioBacktestResultListView, BatchPortfolioBacktestView

app_name = 'backtest'

urlpatterns = [
    # 新的组合回测API
    path('portfolio/run/', BatchPortfolioBacktestView.as_view(), name='run-portfolio-backtest'),
    
    # 新的组合回测结果查询API
    path('portfolio/results/', PortfolioBacktestResultListView.as_view(), name='list-portfolio-results'),
]

