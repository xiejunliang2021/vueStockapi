from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import ListAPIView
from .models import PortfolioBacktest
from .serializers import BatchBacktestRequestSerializer, PortfolioBacktestSerializer
from .tasks import run_portfolio_backtest

class PortfolioBacktestResultListView(ListAPIView):
    """获取所有组合回测结果的列表视图。"""
    queryset = PortfolioBacktest.objects.all()
    serializer_class = PortfolioBacktestSerializer
    filterset_fields = ['strategy_name', 'start_date', 'end_date']

class BatchPortfolioBacktestView(APIView):
    """
    执行新的、基于投资组合的批量回测任务。
    """
    def post(self, request, *args, **kwargs):
        serializer = BatchBacktestRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        validated_data = serializer.validated_data
        filters = validated_data['filters']
        backtest_params = validated_data['backtest_params']

        # 启动新的组合回测任务
        task = run_portfolio_backtest.delay(
            filters=filters,
            backtest_params=backtest_params
        )

        return Response(
            {"message": "组合回测任务已启动", "task_id": task.id},
            status=status.HTTP_202_ACCEPTED
        )


