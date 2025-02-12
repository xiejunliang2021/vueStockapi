from django.db import models

class PolicyDetails2(models.Model):
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

