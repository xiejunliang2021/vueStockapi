from datetime import date
from basic.services.strategy_service import StrategyService

service = StrategyService(db_alias='default')
signals = service.get_signals_for_backtest(
    start_date=date(2023, 1, 1),
    end_date=date(2025, 6, 30),
    strategy_type='龙回头'
)
print(f"找到 {len(signals)} 个信号")