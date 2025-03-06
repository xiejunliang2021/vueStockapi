from django.db import models
from django.db.models import F

class WeighingRecord(models.Model):
    license_plate = models.CharField(max_length=20, verbose_name="车牌号")  # 车牌号
    tare_weight = models.IntegerField(verbose_name="皮重（kg）")  # 皮重（kg）
    gross_weight = models.IntegerField(verbose_name="毛重（kg）")  # 毛重（kg）
    net_weight = models.IntegerField(editable=False, verbose_name="净重（kg）")  # 净重（kg），不可编辑字段，自动计算
    cargo_spec = models.CharField(max_length=100, verbose_name="货物规格")  # 货物规格
    receiving_unit = models.CharField(max_length=255, verbose_name="收货单位")  # 收货单位
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")  # 更新时间，自动更新为当前时间

    def save(self, *args, **kwargs):
        # 计算净重，并在保存时设置
        self.net_weight = self.gross_weight - self.tare_weight
        super(WeighingRecord, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.license_plate} - {self.cargo_spec}"

    class Meta:
        verbose_name = "称重记录"
        verbose_name_plural = "称重记录"
