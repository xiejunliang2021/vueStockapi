from django.contrib import admin
# 删除这些导入，因为它们已经在 django_celery_beat 中注册
# from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule

# 删除这些注册
# admin.site.register(PeriodicTask)
# admin.site.register(IntervalSchedule)
# admin.site.register(CrontabSchedule)

# 如果你需要注册你自己的模型，可以在这里添加
from .models import PolicyDetails, Code, TradingCalendar, StockDailyData, StrategyStats

@admin.register(PolicyDetails)
class PolicyDetailsAdmin(admin.ModelAdmin):
    list_display = ['stock', 'date', 'strategy_type', 'current_status']
    list_filter = ['strategy_type', 'current_status']
    search_fields = ['stock__ts_code', 'stock__name']

@admin.register(Code)
class CodeAdmin(admin.ModelAdmin):
    list_display = ['ts_code', 'name', 'industry', 'list_status']
    list_filter = ['industry', 'list_status']
    search_fields = ['ts_code', 'name']

@admin.register(TradingCalendar)
class TradingCalendarAdmin(admin.ModelAdmin):
    list_display = ['date', 'is_trading_day', 'remark']
    list_filter = ['is_trading_day']
    search_fields = ['date', 'remark']

@admin.register(StockDailyData)
class StockDailyDataAdmin(admin.ModelAdmin):
    list_display = ['stock', 'trade_date', 'open', 'close', 'high', 'low']
    list_filter = ['trade_date']
    search_fields = ['stock__ts_code', 'stock__name']

@admin.register(StrategyStats)
class StrategyStatsAdmin(admin.ModelAdmin):
    list_display = ['date', 'stock', 'total_signals', 'success_rate']
    list_filter = ['date']
    search_fields = ['stock__ts_code', 'stock__name']
