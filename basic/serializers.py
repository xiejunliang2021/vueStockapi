from rest_framework import serializers
from .models import PolicyDetails, Code, TradingCalendar, StrategyStats
from datetime import date

class PolicyDetailsSerializer(serializers.ModelSerializer):
    """策略详情序列化器"""
    first_buy_time = serializers.DateField(format="%Y-%m-%d", required=False, allow_null=True)
    second_buy_time = serializers.DateField(format="%Y-%m-%d", required=False, allow_null=True)
    take_profit_time = serializers.DateField(format="%Y-%m-%d", required=False, allow_null=True)
    stop_loss_time = serializers.DateField(format="%Y-%m-%d", required=False, allow_null=True)
    date = serializers.DateField(format="%Y-%m-%d")
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    updated_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    
    class Meta:
        model = PolicyDetails
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class CodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Code
        fields = '__all__'


class TradingCalendarSerializer(serializers.ModelSerializer):
    """交易日历序列化器"""
    
    class Meta:
        model = TradingCalendar
        fields = ['date', 'is_trading_day', 'remark']
        
    def validate_date(self, value):
        """验证日期格式"""
        if value is None:
            raise serializers.ValidationError("日期不能为空")
        return value

class StockPatternAnalysisSerializer(serializers.Serializer):
    """股票模式分析序列化器"""
    trade_date = serializers.DateField(
        required=True,
        error_messages={'required': '请提供分析日期'}
    )
    
    def validate_trade_date(self, value):
        if value > date.today():
            raise serializers.ValidationError("分析日期不能超过今天")
        return value

class StockPatternResultSerializer(serializers.Serializer):
    """股票模式分析结果序列化器"""
    stock = serializers.CharField()
    pattern_dates = serializers.ListField(child=serializers.DateField())
    history_dates = serializers.ListField(child=serializers.DateField())
    max_high = serializers.FloatField()
    min_low = serializers.FloatField()
    avg_price = serializers.FloatField()

class StrategyStatsSerializer(serializers.ModelSerializer):
    """策略统计序列化器"""
    stock_name = serializers.CharField(source='stock.name', read_only=True)
    stock_code = serializers.CharField(source='stock.ts_code', read_only=True)

    class Meta:
        model = StrategyStats
        fields = [
            'id', 'date', 'stock', 'stock_name', 'stock_code',
            'total_signals', 'first_buy_success', 'second_buy_success',
            'failed_signals', 'success_rate', 'avg_hold_days',
            'max_drawdown', 'profit_0_3', 'profit_3_5', 'profit_5_7',
            'profit_7_10', 'profit_above_10', 'created_at'
        ]
        read_only_fields = ['created_at']

    def validate_stock(self, value):
        if value and not Code.objects.filter(pk=value).exists():
            raise serializers.ValidationError("指定的股票不存在")
        return value
