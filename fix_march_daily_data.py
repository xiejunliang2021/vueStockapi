#!/usr/bin/env python
"""
查询并补充2026年3月的股票日线数据
功能：
1. 查询3月份哪些交易日有数据
2. 找出缺失的交易日
3. 从Tushare补充缺失数据
"""
import os
import sys
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vueStockapi.settings')
django.setup()

from datetime import date
from basic.models import StockDailyData, TradingCalendar, Code
from basic.utils import StockDataFetcher
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_march_data():
    """查询3月份日线数据状况"""
    print("=" * 60)
    print("  2026年3月日线数据检查报告")
    print("=" * 60)

    # 1. 查询3月份所有交易日
    march_trading_days = TradingCalendar.objects.filter(
        date__year=2026,
        date__month=3,
        is_trading_day=True
    ).order_by('date')

    if not march_trading_days.exists():
        print("❌ 交易日历中没有2026年3月的数据，请先更新交易日历！")
        return [], []

    print(f"\n📅 3月份共有 {march_trading_days.count()} 个交易日：")
    for day in march_trading_days:
        print(f"   {day.date}")

    # 2. 查询3月份各交易日的数据量
    print(f"\n📊 各交易日数据量统计：")
    print(f"{'日期':<15} {'数据条数':<12} {'状态'}")
    print("-" * 40)

    dates_with_data = set()
    dates_missing = []

    for trading_day in march_trading_days:
        count = StockDailyData.objects.filter(
            trade_date=trading_day.date
        ).count()

        if count > 0:
            dates_with_data.add(trading_day.date)
            status = f"✅ 正常"
        else:
            dates_missing.append(trading_day.date)
            status = f"❌ 缺失"

        print(f"{str(trading_day.date):<15} {count:<12} {status}")

    # 3. 汇总
    print(f"\n📋 汇总：")
    print(f"   有数据的交易日：{len(dates_with_data)} 天")
    print(f"   缺失数据的交易日：{len(dates_missing)} 天")

    if dates_missing:
        print(f"\n⚠️  以下交易日数据缺失：")
        for d in dates_missing:
            print(f"   - {d}")

    return list(dates_with_data), dates_missing


def supplement_missing_data(dates_missing):
    """补充缺失的日线数据"""
    if not dates_missing:
        print("\n✅ 3月份日线数据完整，无需补充！")
        return

    print(f"\n🔄 开始补充 {len(dates_missing)} 个交易日的数据...")
    print("=" * 60)

    fetcher = StockDataFetcher()
    total_codes = Code.objects.count()
    print(f"   数据库中共有 {total_codes} 只股票")

    success_dates = []
    failed_dates = []

    for missing_date in sorted(dates_missing):
        date_str = missing_date.strftime('%Y-%m-%d')
        print(f"\n▶ 正在补充 {date_str} 的数据...")

        try:
            result = fetcher.update_all_stocks_daily_data(trade_date=date_str)
            status = result.get('status', 'unknown')

            if status == 'success':
                saved = result.get('total_saved', 0)
                print(f"   ✅ 成功！写入 {saved} 条记录")
                success_dates.append(date_str)
            elif status == 'skipped':
                print(f"   ⏭  已跳过：{result.get('message', '')}")
                success_dates.append(date_str)  # 跳过也算成功（可能已存在）
            else:
                print(f"   ❌ 失败：{result.get('message', '未知错误')}")
                failed_dates.append(date_str)

        except Exception as e:
            print(f"   ❌ 出现异常：{str(e)}")
            failed_dates.append(date_str)

    # 汇总补充结果
    print(f"\n{'=' * 60}")
    print(f"  数据补充完成！")
    print(f"{'=' * 60}")
    print(f"   ✅ 成功补充：{len(success_dates)} 天")
    if failed_dates:
        print(f"   ❌ 补充失败：{len(failed_dates)} 天")
        for d in failed_dates:
            print(f"      - {d}")


def final_check():
    """最终数据验证"""
    print(f"\n{'=' * 60}")
    print(f"  最终验证结果")
    print(f"{'=' * 60}")

    march_trading_days = TradingCalendar.objects.filter(
        date__year=2026,
        date__month=3,
        is_trading_day=True
    ).order_by('date')

    all_ok = True
    for trading_day in march_trading_days:
        count = StockDailyData.objects.filter(
            trade_date=trading_day.date
        ).count()

        if count == 0:
            print(f"   ❌ {trading_day.date} 仍然缺失数据！")
            all_ok = False
        else:
            print(f"   ✅ {trading_day.date}：{count} 条记录")

    if all_ok:
        print(f"\n🎉 3月份所有交易日的日线数据均已完整！")
    else:
        print(f"\n⚠️  部分数据仍有缺失，请检查Tushare接口或手动处理。")


if __name__ == '__main__':
    print("\n🚀 开始执行3月日线数据检查与补充\n")

    # 第一步：检查数据状态
    dates_with_data, dates_missing = check_march_data()

    # 第二步：补充缺失数据
    supplement_missing_data(dates_missing)

    # 第三步：最终验证
    final_check()

    print(f"\n✅ 任务完成！\n")
