from rest_framework import serializers
from .models import PolicyDetails, Code, TradingCalendar
from datetime import date

class PolicyDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyDetails
        fields = '__all__'


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
