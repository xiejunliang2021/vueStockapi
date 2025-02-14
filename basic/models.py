from django.db import models
from django.utils import timezone

class PolicyDetails(models.Model):
    """策略详情模型
    
    该模型用于存储股票交易策略的详细信息，包括买卖点位、状态跟踪等
    
    字段说明：
    - stock: 关联的股票代码，外键关联到Code模型
    - date: 策略生成日期，记录策略产生的具体日期
    - first_buy_point: 第一买点价格，通常是前三天非涨停股票的最高点
    - second_buy_point: 第二买点价格，通常是最高点和最低点的平均价
    - stop_loss_point: 止损价格，用于控制风险的最低价位
    - take_profit_point: 止盈价格，达到该价格考虑获利了结
    - strategy_type: 策略类型，用于区分不同的交易策略
    - signal_strength: 信号强度，表示策略信号的可信度（0-1）
    - success_rate: 历史成功率，该策略的历史表现（0-100）
    - holding_profit: 持仓盈利百分比，当前持仓的盈利情况
    - holding_price: 实际持仓价格，策略执行时的实际买入价格
    - current_status: 当前策略状态（S-成功，F-失败，L-进行中）
    - created_at: 记录创建时间
    - updated_at: 记录更新时间
    """
    
    STATUS_CHOICES = [
        ('S', '成功'),  # 策略达到预期目标
        ('F', '失败'),  # 策略触发止损
        ('L', '进行中'), # 策略正在执行中
    ]

    stock = models.ForeignKey('Code', on_delete=models.CASCADE, verbose_name="股票")
    date = models.DateField(verbose_name="日期")
    first_buy_point = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="第一买点")
    second_buy_point = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="第二买点", 
        null=True, 
        blank=True
    )
    stop_loss_point = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="止损点")
    take_profit_point = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="止盈点")
    strategy_type = models.CharField(max_length=50, verbose_name="策略类型", default='CONTINUOUS_LIMIT_UP')
    signal_strength = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        verbose_name="信号强度",
        default=0.80
    )
    success_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        verbose_name="历史成功率",
        default=0.00
    )
    holding_profit = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0, 
        verbose_name="持仓盈利"
    )
    holding_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0, 
        verbose_name="持仓价格"
    )
    current_status = models.CharField(
        max_length=1, 
        choices=STATUS_CHOICES, 
        default='L', 
        verbose_name="当前状态"
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="创建时间"
    )
    updated_at = models.DateTimeField(
        auto_now=True, 
        verbose_name="更新时间"
    )

    class Meta:
        verbose_name = "策略详情"
        verbose_name_plural = "策略详情"
        unique_together = ('stock', 'date', 'strategy_type')
        ordering = ['-date', 'stock']  # 添加默认排序
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['stock', 'date']),
            models.Index(fields=['current_status']),
        ]

    def __str__(self):
        return f"{self.stock.name} - {self.date}"

    def save(self, *args, **kwargs):
        # 如果是新创建的记录
        if not self.pk:
            self.created_at = timezone.now()
        super().save(*args, **kwargs)


class Code(models.Model):
    """股票代码模型
    
    用于存储股票的基本信息
    
    字段说明：
    - ts_code: Tushare专用的股票代码
    - symbol: 股票代码（不带市场标识）
    - name: 股票名称
    - area: 所属地区
    - industry: 所属行业
    - market: 市场类型（主板/创业板/科创板等）
    - list_status: 上市状态（L-上市 D-退市 P-暂停上市）
    - list_date: 上市日期
    - version: 乐观锁字段，用于并发控制
    """
    LIST_STATUS_CHOICES = [
        ('L', '上市'),
        ('D', '退市'),
        ('P', '暂停上市'),
    ]

    ts_code = models.CharField(max_length=20, primary_key=True, db_index=True, verbose_name="股票代码")
    symbol = models.CharField(max_length=20, unique=True, verbose_name="代码")
    name = models.CharField(max_length=100, verbose_name="股票名称")
    area = models.CharField(max_length=50, verbose_name="区域")
    industry = models.CharField(max_length=100, verbose_name="所属行业")
    market = models.CharField(max_length=50, verbose_name="市场类型")
    list_status = models.CharField(max_length=1, choices=LIST_STATUS_CHOICES, verbose_name="上市状态")
    list_date = models.DateField(verbose_name="上市日期")
    version = models.IntegerField(default=0)  # 乐观锁字段

    class Meta:
        verbose_name = "股票信息"
        verbose_name_plural = "股票信息"

    def __str__(self):
        return f"{self.ts_code} - {self.name}"


class StockDailyData(models.Model):
    """股票日线数据模型
    
    存储股票的每日交易数据
    
    字段说明：
    - stock: 关联的股票代码
    - trade_date: 交易日期
    - open: 开盘价
    - high: 最高价
    - low: 最低价
    - close: 收盘价
    - volume: 成交量（手）
    - amount: 成交额（元）
    """
    stock = models.ForeignKey(Code, on_delete=models.CASCADE, verbose_name="股票")
    trade_date = models.DateField(verbose_name="交易日期")
    open = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="开盘价")
    high = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="最高价")
    low = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="最低价")
    close = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="收盘价")
    volume = models.BigIntegerField(verbose_name="成交量")
    amount = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="成交额")

    class Meta:
        verbose_name = "股票日线数据"
        verbose_name_plural = "股票日线数据"
        unique_together = ('stock', 'trade_date')

