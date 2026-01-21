from django.db import models

class PortfolioBacktest(models.Model):
    """组合回测结果模型"""
    strategy_name = models.CharField(max_length=100, verbose_name="策略名称", db_index=True)
    
    # 回测参数
    start_date = models.DateField(verbose_name="开始日期")
    end_date = models.DateField(verbose_name="结束日期")
    initial_capital = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="初始资金")
    capital_per_stock_ratio = models.DecimalField(max_digits=5, decimal_places=4, verbose_name="单票资金占比")

    # 回测结果
    final_capital = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="最终资金")
    total_profit = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="总盈利")
    total_return = models.DecimalField(max_digits=10, decimal_places=4, verbose_name="总收益率")
    max_drawdown = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True, verbose_name="最大回撤")
    max_profit = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="最大盈利")
    
    # 统计信息
    total_trades = models.IntegerField(default=0, verbose_name="总交易次数")
    winning_trades = models.IntegerField(default=0, verbose_name="盈利次数")
    losing_trades = models.IntegerField(default=0, verbose_name="亏损次数")
    win_rate = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True, verbose_name="胜率")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "组合回测结果"
        verbose_name_plural = "组合回测结果"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.strategy_name} ({self.start_date} to {self.end_date}) - Return: {self.total_return:.2%}"

class TradeLog(models.Model):
    """详细交易记录模型"""
    portfolio_backtest = models.ForeignKey(PortfolioBacktest, related_name='trades', on_delete=models.CASCADE, verbose_name="所属组合回测")
    stock_code = models.CharField(max_length=20, verbose_name="股票代码")
    
    buy_date = models.DateField(verbose_name="买入日期")
    buy_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="买入价格")
    
    sell_date = models.DateField(verbose_name="卖出日期")
    sell_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="卖出价格")
    sell_reason = models.CharField(
        max_length=20,
        verbose_name="卖出原因",
        choices=[
            ('take_profit', '止盈'),
            ('stop_loss', '止损'),
            ('timeout', '超时'),
        ],
        default='timeout',
        null=True,
        blank=True
    )
    
    quantity = models.IntegerField(verbose_name="数量")
    profit = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="单笔盈利")
    return_rate = models.DecimalField(max_digits=10, decimal_places=4, verbose_name="单笔收益率")
    strategy_type = models.CharField(
        max_length=50,
        verbose_name="策略类型",
        default='龙回头',
        null=True,
        blank=True
    )
    
    # 连续涨停策略特有字段
    hold_days = models.IntegerField(
        verbose_name="持仓天数",
        null=True,
        blank=True,
        help_text="实际持仓天数"
    )
    min_diff_to_target = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="最小差值",
        null=True,
        blank=True,
        help_text="买点确定后，最低价与买点的最小差值"
    )
    min_diff_date = models.DateField(
        verbose_name="最小差值日期",
        null=True,
        blank=True,
        help_text="最小差值出现的日期"
    )
    days_to_min_diff = models.IntegerField(
        verbose_name="距买点确定天数",
        null=True,
        blank=True,
        help_text="从买点确定到最小差值出现的天数"
    )

    class Meta:
        verbose_name = "交易日志"
        verbose_name_plural = "交易日志"
        ordering = ['buy_date']

    def __str__(self):
        return f"Trade {self.stock_code}: Buy at {self.buy_price}, Sell at {self.sell_price}"

