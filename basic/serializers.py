from rest_framework import serializers
from .models import PolicyDetails, Code, TradingCalendar

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
