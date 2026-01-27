"""
基于Backtrader的回测服务
"""
import backtrader as bt
import pandas as pd
from typing import Dict, List, Optional
from datetime import date, timedelta
from decimal import Decimal
import logging

from basic.services.strategy_service import StrategyService
from ..models import PortfolioBacktest, TradeLog
from ..strategies_backtrader import DragonTurnBacktraderStrategy, PandasData
from ..strategies_limit_break import LimitBreakStrategy
from ..data_feeds import LimitBreakDataFeed
from .oracle_data_service import OracleDataService
from .tushare_data_service import TushareDataService

logger = logging.getLogger(__name__)



class BacktraderBacktestService:
    """基于Backtrader的回测服务"""
    
    def __init__(self):
        self.strategy_service = StrategyService()
    
    def run_backtest(
        self,
        strategy_name: str,
        start_date: date,
        end_date: date,
        initial_capital: Decimal,
        capital_per_stock_ratio: Decimal,
        strategy_type: str = '龙回头',
        hold_timeout_days: int = 60,
        db_alias: str = 'default',
        commission: float = 0.0003,  # 佣金率
        update_policy_status: bool = False  # 是否更新策略状态（避免Oracle连接问题）
    ) -> Dict:
        """
        使用Backtrader执行回测
        
        Returns:
            回测结果字典
        """
        logger.info(f"开始Backtrader回测: {strategy_name}")
        logger.info(f"时间范围: {start_date} 至 {end_date}")
        logger.info(f"初始资金: {initial_capital}, 单票比例: {capital_per_stock_ratio}")
        
        # 1. 获取策略信号
        logger.info("=" * 50)
        logger.info("【阶段1】加载策略信号...")
        signals = self.strategy_service.get_signals_for_backtest(
            start_date=start_date,
            end_date=end_date,
            strategy_type=strategy_type if strategy_type != '全部' else None
        )
        
        if not signals:
            logger.warning("未找到符合条件的策略信号")
            return {
                'status': 'SUCCESS',
                'message': '未找到符合条件的策略信号',
                'result_id': None
            }
        
        logger.info(f"找到 {len(signals)} 个策略信号")
        
        # 2. 组织信号数据
        signals_by_date = {}
        stock_codes = set()
        for signal in signals:
            signals_by_date.setdefault(signal.signal_date, []).append(signal)
            stock_codes.add(signal.stock_code)
        
        stock_codes = list(stock_codes)
        logger.info(f"涉及 {len(stock_codes)} 只股票")
        
        # 3. 获取价格数据
        logger.info("=" * 50)
        logger.info("【阶段2】加载价格数据...")
        extended_end_date = end_date + timedelta(days=hold_timeout_days + 10)
        price_data = self.strategy_service.get_price_data(
            stock_codes=stock_codes,
            start_date=start_date,
            end_date=extended_end_date
        )
        
        if not price_data:
            logger.error("无法获取价格数据")
            return {
                'status': 'FAILURE',
                'message': '无法获取所需的价格数据',
                'result_id': None
            }
        
        # 4. 准备Backtrader
        logger.info("=" * 50)
        logger.info("【阶段3】初始化Backtrader...")
        
        cerebro = bt.Cerebro()
        
        # 设置初始资金
        cerebro.broker.setcash(float(initial_capital))
        
        # 设置佣金
        cerebro.broker.setcommission(commission=commission)
        
        # 添加数据源
        logger.info("添加数据源...")
        data_feeds = self._prepare_data_feeds(price_data, stock_codes, start_date, extended_end_date)
        
        for stock_code, data_feed in data_feeds.items():
            cerebro.adddata(data_feed, name=stock_code)
        
        logger.info(f"已添加 {len(data_feeds)} 个数据源")
        
        # 创建策略结果更新回调（可选）
        update_callback = None
        if update_policy_status:
            def update_callback(stock_code, signal_date, result_type, execution_date, profit_rate=None):
                self.strategy_service.update_strategy_result(
                    stock_code=stock_code,
                    signal_date=signal_date,
                    result_type=result_type,
                    execution_date=execution_date,
                    profit_rate=profit_rate
                )
            logger.info("已启用策略状态更新")
        else:
            logger.info("已禁用策略状态更新（避免数据库连接问题）")
        
        # 添加策略
        cerebro.addstrategy(
            DragonTurnBacktraderStrategy,
            signal_data=signals_by_date,
            hold_timeout_days=hold_timeout_days,
            capital_per_stock_ratio=float(capital_per_stock_ratio),
            update_callback=update_callback
        )
        
        # 添加分析器
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        
        # 5. 运行回测
        logger.info("=" * 50)
        logger.info("【阶段4】执行回测...")
        
        initial_value = cerebro.broker.getvalue()
        logger.info(f"初始资产: {initial_value:,.2f}")
        
        results = cerebro.run()
        strategy_instance = results[0]
        
        final_value = cerebro.broker.getvalue()
        logger.info(f"最终资产: {final_value:,.2f}")
        
        # 6. 提取结果
        logger.info("=" * 50)
        logger.info("【阶段5】提取回测结果...")
        
        # 从策略实例获取交易记录
        trade_logs = strategy_instance.trade_logs
        
        # 从分析器获取指标
        returns_analyzer = strategy_instance.analyzers.returns.get_analysis()
        drawdown_analyzer = strategy_instance.analyzers.drawdown.get_analysis()
        trades_analyzer = strategy_instance.analyzers.trades.get_analysis()
        
        # 计算指标
        total_profit = Decimal(str(final_value - initial_value))
        total_return = Decimal(str((final_value - initial_value) / initial_value))
        max_drawdown = Decimal(str(drawdown_analyzer.get('max', {}).get('drawdown', 0) / 100))
        
        # 统计交易
        total_trades = trades_analyzer.get('total', {}).get('total', 0)
        winning_trades = trades_analyzer.get('won', {}).get('total', 0)
        losing_trades = trades_analyzer.get('lost', {}).get('total', 0)
        win_rate = Decimal(str(winning_trades / total_trades)) if total_trades > 0 else Decimal('0')
        
        logger.info(f"总交易次数: {total_trades}")
        logger.info(f"盈利次数: {winning_trades}, 亏损次数: {losing_trades}")
        logger.info(f"胜率: {win_rate * 100:.2f}%")
        logger.info(f"总收益率: {total_return * 100:.2f}%")
        logger.info(f"最大回撤: {max_drawdown * 100:.2f}%")
        
        # 7. 保存结果
        logger.info("=" * 50)
        logger.info("【阶段6】保存回测结果...")
        
        portfolio_result = PortfolioBacktest.objects.create(
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            capital_per_stock_ratio=capital_per_stock_ratio,
            final_capital=Decimal(str(final_value)),
            total_profit=total_profit,
            total_return=total_return,
            max_drawdown=max_drawdown,
            max_profit=Decimal('0'),  # Backtrader不直接提供，可以后续计算
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate
        )
        
        # 批量保存交易日志
        if trade_logs:
            trade_log_objects = [
                TradeLog(portfolio_backtest=portfolio_result, **log)
                for log in trade_logs
            ]
            TradeLog.objects.bulk_create(trade_log_objects)
            logger.info(f"保存了 {len(trade_logs)} 条交易记录")
        
        logger.info(f"✅ Backtrader回测完成! 结果ID: {portfolio_result.id}")
        
        return {
            'status': 'SUCCESS',
            'message': f'回测完成，共{len(trade_logs)}笔交易',
            'result_id': portfolio_result.id,
            'metrics': {
                'total_return': float(total_return),
                'win_rate': float(win_rate),
                'total_trades': total_trades,
                'max_drawdown': float(max_drawdown),
            }
        }
    
    def _prepare_data_feeds(
        self,
        price_data: Dict,
        stock_codes: List[str],
        start_date: date,
        end_date: date
    ) -> Dict[str, bt.feeds.PandasData]:
        """
        准备Backtrader数据源
        
        Args:
            price_data: 价格数据字典 {date: {stock_code: {price_info}}}
            stock_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            {stock_code: data_feed}
        """
        data_feeds = {}
        
        for stock_code in stock_codes:
            # 提取该股票的所有价格数据
            stock_prices = []
            
            for trade_date in sorted(price_data.keys()):
                if trade_date < start_date or trade_date > end_date:
                    continue
                
                day_prices = price_data.get(trade_date, {})
                stock_price = day_prices.get(stock_code)
                
                if stock_price:
                    stock_prices.append({
                        'datetime': trade_date,
                        'open': stock_price.get('close', 0),  # 如果没有开盘价，用收盘价
                        'high': stock_price.get('high', 0),
                        'low': stock_price.get('low', 0),
                        'close': stock_price.get('close', 0),
                        'volume': 0,  # 可选
                    })
            
            if not stock_prices:
                continue
            
            # 转换为DataFrame
            df = pd.DataFrame(stock_prices)
            df['datetime'] = pd.to_datetime(df['datetime'])
            df.set_index('datetime', inplace=True)
            df = df.sort_index()
            
            # 创建Backtrader数据源
            data_feed = PandasData(dataname=df)
            data_feeds[stock_code] = data_feed
        
        return data_feeds
    
    def run_limit_break_backtest(
        self,
        strategy_name: str,
        start_date: date,
        end_date: date,
        initial_capital: Decimal,
        stock_ids: Optional[List[str]] = None,
        profit_target: float = 0.10,  # 默认改为10%
        stop_loss: float = 0.05,      # 新增参数，默认5%
        max_hold_days: int = 30,
        lookback_days: int = 15,
        max_wait_days: int = 100,
        position_pct: float = 0.02,
        commission: float = 0.001,
        db_alias: str = 'default',
        data_source: str = 'tushare'  # 新增参数：'tushare' 或 'oracle'
    ) -> Dict:
        """
        运行连续涨停策略回测
        
        Args:
            strategy_name: 策略名称
            start_date: 开始日期
            end_date: 结束日期
            initial_capital: 初始资金
            stock_ids: 股票代码列表（可选，默认查询所有L状态股票）
            profit_target: 止盈目标，默认5%
            max_hold_days: 最大持仓天数，默认30天
            lookback_days: 买点计算回溯天数，默认15天
            max_wait_days: 买点等待超时天数，默认100天
            position_pct: 单次买入占总资金比例，默认2%
            commission: 佣金率，默认0.1%
            db_alias: 数据库别名
            data_source: 数据源，'tushare'(默认) 或 'oracle'
            
        Returns:
            回测结果字典
        """
        logger.info(f"开始连续涨停策略回测: {strategy_name}")
        logger.info(f"时间范围: {start_date} 至 {end_date}")
        logger.info(f"初始资金: {initial_capital}")
        logger.info(f"数据源: {data_source.upper()}")
        
        # 1. 获取股票列表
        logger.info("=" * 50)
        logger.info("【阶段1】加载股票列表...")
        
        oracle_service = OracleDataService(db_alias=db_alias)
        
        if stock_ids:
            stocks = [{'stock_id': sid, 'stock_name': f'Stock_{sid}', 'date': start_date} 
                     for sid in stock_ids]
        else:
            # ✅ 修改：根据回测日期范围查询所有股票（不限制策略类型和状态）
            stocks = oracle_service.get_strategy_stocks_by_date_range(
                start_date=start_date,
                end_date=end_date
            )
        
        if not stocks:
            logger.warning("未找到股票")
            return {
                'status': 'SUCCESS',
                'message': '未找到符合条件的股票',
                'result_id': None
            }
        
        logger.info(f"找到 {len(stocks)} 只股票")
        
        # ✅ 初始化数据服务
        if data_source == 'tushare':
            data_service = TushareDataService()
            logger.info("使用 Tushare API 获取数据（前复权）")
        else:
            data_service = oracle_service
            logger.info("使用 Oracle 数据库获取数据")
        
        # 2. 批量回测
        logger.info("=" * 50)
        logger.info("【阶段2】执行批量回测...")
        
        all_trades = []
        total_initial = Decimal('0')
        total_final = Decimal('0')
        success_count = 0
        failed_count = 0
        
        for idx, stock_info in enumerate(stocks, 1):
            stock_id = stock_info['stock_id']
            stock_name = stock_info.get('stock_name', stock_id)
            anchor_date = stock_info.get('date', start_date)  # ✅ 使用股票策略日期作为锚点
            
            logger.info(f"[{idx}/{len(stocks)}] 回测 {stock_name} ({stock_id}), 锚点日期: {anchor_date}")
            
            # ✅ 获取日线数据 - 使用股票策略日期作为锚点
            df_data = data_service.get_stock_daily_data(
                stock_id=stock_id,
                anchor_date=anchor_date,  # 使用股票策略日期
                days_before=lookback_days + 10,
                days_after=max_hold_days + 10
            )
            
            if df_data is None or df_data.empty:
                logger.warning(f"{stock_id} 无数据，跳过")
                failed_count += 1
                continue
            
            # 创建 Cerebro
            cerebro = bt.Cerebro()
            cerebro.broker.setcash(float(initial_capital))
            cerebro.broker.setcommission(commission=commission)
            
            # 添加数据源
            data_feed = LimitBreakDataFeed(dataname=df_data)
            cerebro.adddata(data_feed)
            
            # 添加策略
            cerebro.addstrategy(
                LimitBreakStrategy,
                profit_target=profit_target,
                stop_loss=stop_loss,  # ✅ 传递止损参数
                max_hold_days=max_hold_days,
                lookback_days=lookback_days,
                max_wait_days=max_wait_days,
                position_pct=position_pct,
                debug_mode=False
            )
            
            # 添加分析器
            cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
            cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
            cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
            
            # 运行
            initial_value = cerebro.broker.getvalue()
            results = cerebro.run()
            strategy_instance = results[0]
            final_value = cerebro.broker.getvalue()
            
            # 提取交易记录
            for trade_record in strategy_instance.trades_record:
                trade_log = {
                    'stock_code': stock_id,
                    'buy_date': trade_record['买入日期'],
                    'buy_price': Decimal(str(trade_record['买入价格'])),
                    'sell_date': trade_record['卖出日期'],
                    'sell_price': Decimal(str(trade_record['卖出价格'])),
                    'quantity': 100,  # 默认值，策略中未记录
                    'profit': Decimal(str(trade_record['盈亏金额'])),
                    'return_rate': Decimal(str(trade_record['收益率'].replace('%', ''))) / 100,
                    'sell_reason': trade_record['卖出原因'],
                    'strategy_type': '连续涨停',
                    # 扩展字段
                    'hold_days': trade_record['持仓天数'],
                    'min_diff_to_target': Decimal(str(trade_record['最小差值'])) if trade_record['最小差值'] != 'N/A' else None,
                    'min_diff_date': trade_record['最小差值日期'] if trade_record['最小差值日期'] != 'N/A' else None,
                    'days_to_min_diff': trade_record['距买点确定天数'] if trade_record['距买点确定天数'] != 'N/A' else None,
                }
                all_trades.append(trade_log)
            
            total_initial += Decimal(str(initial_value))
            total_final += Decimal(str(final_value))
            
            if len(strategy_instance.trades_record) > 0:
                success_count += 1
                logger.info(f"✓ {stock_name}: {len(strategy_instance.trades_record)}笔交易")
            else:
                logger.info(f"- {stock_name}: 无交易")
        
        # 3. 计算汇总指标
        logger.info("=" * 50)
        logger.info("【阶段3】计算汇总指标...")
        
        total_profit = total_final - total_initial
        total_return = total_profit / total_initial if total_initial > 0 else Decimal('0')
        
        total_trades = len(all_trades)
        winning_trades = sum(1 for t in all_trades if t['profit'] > 0)
        losing_trades = sum(1 for t in all_trades if t['profit'] <= 0)
        win_rate = Decimal(str(winning_trades / total_trades)) if total_trades > 0 else Decimal('0')
        
        # 计算最大回撤（简化版，从daily_values计算）
        # 这里简化处理，实际可以从每个股票的回测中提取
        max_drawdown = Decimal('0')  # 待实现
        
        logger.info(f"总交易次数: {total_trades}")
        logger.info(f"盈利次数: {winning_trades}, 亏损次数: {losing_trades}")
        logger.info(f"胜率: {win_rate * 100:.2f}%")
        logger.info(f"总收益率: {total_return * 100:.2f}%")
        
        # 4. 保存结果到MySQL
        logger.info("=" * 50)
        logger.info("【阶段4】保存回测结果...")
        
        portfolio_result = PortfolioBacktest.objects.create(
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=total_initial,
            capital_per_stock_ratio=Decimal(str(position_pct)),  # 单票资金占比
            final_capital=total_final,
            total_profit=total_profit,
            total_return=total_return,
            max_drawdown=max_drawdown,
            max_profit=Decimal('0'),  # 待实现
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate
        )
        
        # 批量保存交易日志
        if all_trades:
            trade_log_objects = [
                TradeLog(portfolio_backtest=portfolio_result, **log)
                for log in all_trades
            ]
            TradeLog.objects.bulk_create(trade_log_objects)
            logger.info(f"保存了 {len(all_trades)} 条交易记录")
        
        logger.info(f"✅ 连续涨停策略回测完成! 结果ID: {portfolio_result.id}")
        
        return {
            'status': 'SUCCESS',
            'message': f'回测完成，共{len(all_trades)}笔交易',
            'result_id': portfolio_result.id,
            'metrics': {
                'total_return': float(total_return),
                'win_rate': float(win_rate),
                'total_trades': total_trades,
                'max_drawdown': float(max_drawdown),
                'stocks_tested': len(stocks),
                'stocks_with_trades': success_count,
            }
        }
