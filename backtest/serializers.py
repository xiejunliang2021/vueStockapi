from rest_framework import serializers
from .models import PortfolioBacktest, TradeLog

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
    # 回测引擎选择
    use_backtrader = serializers.BooleanField(default=False, help_text="是否使用Backtrader引擎")
    commission = serializers.FloatField(default=0.0003, min_value=0.0, max_value=0.1, help_text="佣金率")
    # 策略参数
    profit_target = serializers.FloatField(default=0.10, min_value=0.01, max_value=10.0, help_text="止盈目标 (0.10 = 10%)")
    stop_loss = serializers.FloatField(default=0.05, min_value=0.01, max_value=1.0, help_text="止损阈值 (0.05 = 5%)")
    # 数据源选择
    data_source = serializers.ChoiceField(
        choices=['tushare', 'oracle'],
        default='tushare',
        help_text="数据源：tushare(前复权) 或 oracle"
    )

class BatchFiltersSerializer(serializers.Serializer):
    """批处理回测的过滤条件"""
    strategy_name = serializers.CharField(max_length=100, required=True, help_text="策略名称，用于标识本次回测")
    strategy_type = serializers.CharField(max_length=50, default='龙回头', help_text="策略类型（龙回头/连续涨停）")
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

class TradeLogSerializer(serializers.ModelSerializer):
    """交易日志序列化器"""
    sell_reason_display = serializers.CharField(source='get_sell_reason_display', read_only=True)
    
    class Meta:
        model = TradeLog
        fields = '__all__'

