from django.db import models

class PolicyDetails(models.Model):
    stock_name = models.CharField(max_length=100, verbose_name="股票名称")
    date = models.DateField(verbose_name="日期")
    first_buy_point = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="第一买点")
    second_buy_point = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="第二买点", null=True, blank=True)
    stop_loss_point = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="止损点")
    take_profit_point = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="止盈点")

    class Meta:
        verbose_name = "策略详情"
        verbose_name_plural = "策略详情"
        unique_together = ('stock_name', 'date')

    def __str__(self):
        return f"{self.stock_name} - {self.date}"


class Code(models.Model):
    """股票代码模型"""
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

