from rest_framework import serializers
from .models import PortfolioBacktest

class PortfolioBacktestSerializer(serializers.ModelSerializer):
    """组合回测结果序列化器"""
    trades = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = PortfolioBacktest
        fields = '__all__'

class BacktestParamsSerializer(serializers.Serializer):
    """批处理回测的执行参数"""
    buy_timeout_days = serializers.IntegerField(default=10, min_value=1)
    hold_timeout_days = serializers.IntegerField(default=60, min_value=1)
    db_alias = serializers.CharField(default='default')
    # 新增资金管理参数
    total_capital = serializers.FloatField(default=1000000.0, min_value=1.0, help_text="初始总资金")
    capital_per_stock_ratio = serializers.FloatField(default=0.1, min_value=0.01, max_value=1.0, help_text="单只股票资金占比")

class BatchFiltersSerializer(serializers.Serializer):
    """批处理回测的过滤条件"""
    strategy_name = serializers.CharField(max_length=100, required=True, help_text="策略名称，用于标识本次回测")
    stock_code = serializers.CharField(max_length=20, required=False, help_text="股票的 ts_code (可选)")
    start_date = serializers.DateField(required=True, help_text="回测起始日期 (YYYY-MM-DD)")
    end_date = serializers.DateField(required=True, help_text="回测结束日期 (YYYY-MM-DD)")

    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("结束日期不能早于开始日期")
        return data

class BatchBacktestRequestSerializer(serializers.Serializer):
    """批处理回测的完整请求体验证器"""
    filters = BatchFiltersSerializer(required=True)
    backtest_params = BacktestParamsSerializer(required=True)

