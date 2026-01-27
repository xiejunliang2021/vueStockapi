"""
回测服务层：封装回测逻辑
"""
from typing import List, Dict, Optional
from datetime import date, timedelta
from decimal import Decimal
import logging
import pandas as pd

from basic.services.strategy_service import StrategyService, StrategySignal
from ..models import PortfolioBacktest, TradeLog

logger = logging.getLogger(__name__)


class Position:
    """持仓信息"""
    
    def __init__(self, stock_code, quantity, entry_price, entry_date, strategy_type='龙回头'):
        self.stock_code = stock_code
        self.quantity = quantity
        self.entry_price = Decimal(str(entry_price))
        self.entry_date = entry_date
        self.strategy_type = strategy_type
    
    def get_value(self, current_price):
        """计算当前市值"""
        return self.quantity * Decimal(str(current_price))


class Portfolio:
    """投资组合"""
    
    def __init__(self, initial_capital: Decimal):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.history = []
    
    def can_buy(self, capital_needed: Decimal) -> bool:
        """检查是否有足够资金买入"""
        return self.cash >= capital_needed
    
    def buy(self, stock_code: str, price: float, date: date, 
            capital_to_invest: Decimal, strategy_type: str = '龙回头') -> bool:
        """
        执行买入操作
        
        Returns:
            是否成功买入
        """
        if not self.can_buy(capital_to_invest):
            logger.warning(f"{date}: 资金不足，无法买入 {stock_code}")
            return False
        
        price = Decimal(str(price))
        # 100股为一手
        quantity = int(capital_to_invest / price / 100) * 100
        
        if quantity == 0:
            logger.warning(f"{date}: 计算股数为0，无法买入 {stock_code}")
            return False
        
        cost = quantity * price
        self.cash -= cost
        
        self.positions[stock_code] = Position(
            stock_code=stock_code,
            quantity=quantity,
            entry_price=price,
            entry_date=date,
            strategy_type=strategy_type
        )
        
        logger.info(f"{date}: 买入 {stock_code} {quantity}股 @ {price:.2f}, 花费 {cost:.2f}")
        return True
    
    def sell(self, stock_code: str, price: float, date: date) -> Optional[Dict]:
        """
        执行卖出操作
        
        Returns:
            交易记录字典，如果卖出失败返回None
        """
        if stock_code not in self.positions:
            logger.warning(f"{date}: {stock_code} 不在持仓中")
            return None
        
        position = self.positions.pop(stock_code)
        price = Decimal(str(price))
        proceeds = position.quantity * price
        self.cash += proceeds
        
        # 计算盈亏
        profit = (price - position.entry_price) * position.quantity
        return_rate = (price / position.entry_price) - Decimal('1')
        
        trade_log = {
            'stock_code': stock_code,
            'buy_date': position.entry_date,
            'buy_price': position.entry_price,
            'sell_date': date,
            'sell_price': price,
            'quantity': position.quantity,
            'profit': profit,
            'return_rate': return_rate,
            'strategy_type': position.strategy_type,
        }
        
        logger.info(f"{date}: 卖出 {stock_code} {position.quantity}股 @ {price:.2f}, "
                   f"盈亏 {profit:.2f} ({return_rate*100:.2f}%)")
        return trade_log
    
    def get_total_value(self, current_prices: Dict[str, Dict]) -> Decimal:
        """计算总资产"""
        stock_value = Decimal('0')
        for stock_code, position in self.positions.items():
            price_data = current_prices.get(stock_code, {})
            price = price_data.get('close', position.entry_price)
            stock_value += position.get_value(price)
        
        return self.cash + stock_value
    
    def record_daily_value(self, date: date, current_prices: Dict):
        """记录每日资产"""
        total_value = self.get_total_value(current_prices)
        self.history.append({'date': date, 'value': total_value})


class BacktestStrategy:
    """回测策略基类"""
    
    def should_sell(self, position: Position, current_price_data: Dict,
                   current_date: date, signal: Optional[StrategySignal] = None) -> tuple:
        """
        判断是否应该卖出
        
        Returns:
            (是否卖出, 卖出原因)
        """
        raise NotImplementedError
    
    def should_buy(self, signal: StrategySignal, current_price_data: Dict,
                   current_date: date) -> tuple:
        """
        判断是否应该买入
        
        Returns:
            (是否买入, 买入价格)
        """
        raise NotImplementedError


class DragonTurnStrategy(BacktestStrategy):
    """龙回头策略"""
    
    def __init__(self, hold_timeout_days: int = 60):
        self.hold_timeout_days = hold_timeout_days
    
    def should_sell(self, position: Position, current_price_data: Dict,
                   current_date: date, signal: Optional[StrategySignal] = None) -> tuple:
        """卖出条件判断"""
        if not current_price_data:
            return False, ''
        
        high = current_price_data.get('high', 0)
        low = current_price_data.get('low', 0)
        
        # 1. 检查持仓超时
        days_held = (current_date - position.entry_date).days
        if days_held >= self.hold_timeout_days:
            return True, 'timeout'
        
        # 2. 检查止盈（需要信号数据）
        if signal and high >= float(signal.take_profit_point):
            return True, 'take_profit'
        
        # 3. 检查止损
        if signal and low <= float(signal.stop_loss_point):
            return True, 'stop_loss'
        
        return False, ''
    
    def should_buy(self, signal: StrategySignal, current_price_data: Dict,
                   current_date: date) -> tuple:
        """买入条件判断"""
        if not current_price_data:
            return False, 0
        
        low = current_price_data.get('low', 0)
        close = current_price_data.get('close', 0)
        
        # 如果当天的最低价触及第一买点，则买入
        if low <= float(signal.first_buy_point):
            # 使用第一买点价格买入（假设能成交）
            buy_price = float(signal.first_buy_point)
            return True, buy_price
        
        return False, 0


class BacktestService:
    """回测服务"""
    
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
        db_alias: str = 'default'
    ) -> Dict:
        """
        执行回测
        
        Returns:
            回测结果字典
        """
        logger.info(f"开始回测: {strategy_name}")
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
        
        # 2. 获取价格数据
        logger.info("=" * 50)
        logger.info("【阶段2】加载价格数据...")
        stock_codes = list(set(s.stock_code for s in signals))
        logger.info(f"涉及股票数量: {len(stock_codes)}")
        
        # 扩展结束日期以包含持仓超时期间的数据
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
        
        # 3. 初始化回测环境
        logger.info("=" * 50)
        logger.info("【阶段3】初始化回测环境...")
        portfolio = Portfolio(initial_capital)
        backtest_strategy = DragonTurnStrategy(hold_timeout_days)
        trade_logs = []
        
        # 按日期组织信号
        signals_by_date = {}
        signals_by_stock = {}  # {stock_code: {date: signal}}
        for signal in signals:
            signals_by_date.setdefault(signal.signal_date, []).append(signal)
            if signal.stock_code not in signals_by_stock:
                signals_by_stock[signal.stock_code] = {}
            signals_by_stock[signal.stock_code][signal.signal_date] = signal
        
        # 4. 回测循环
        logger.info("=" * 50)
        logger.info("【阶段4】执行回测循环...")
        trading_days = sorted(price_data.keys())
        logger.info(f"交易日总数: {len(trading_days)}")
        
        for idx, trade_date in enumerate(trading_days, 1):
            if trade_date < start_date:
                continue
            
            if idx % 50 == 0:
                logger.info(f"处理进度: {idx}/{len(trading_days)}")
            
            current_prices = price_data.get(trade_date, {})
            
            # a. 检查卖出条件
            for stock_code in list(portfolio.positions.keys()):
                position = portfolio.positions[stock_code]
                price_data_for_stock = current_prices.get(stock_code, {})
                
                # 获取该股票的信号
                stock_signals = signals_by_stock.get(stock_code, {})
                signal = stock_signals.get(position.entry_date)
                
                should_sell, sell_reason = backtest_strategy.should_sell(
                    position, price_data_for_stock, trade_date, signal
                )
                
                if should_sell:
                    sell_price = price_data_for_stock.get('close', position.entry_price)
                    trade_log = portfolio.sell(stock_code, sell_price, trade_date)
                    
                    if trade_log:
                        trade_log['sell_reason'] = sell_reason
                        trade_logs.append(trade_log)
                        
                        # 更新策略结果
                        if signal:
                            profit_rate = float(trade_log['return_rate'])
                            self.strategy_service.update_strategy_result(
                                stock_code=stock_code,
                                signal_date=signal.signal_date,
                                result_type=sell_reason,
                                execution_date=trade_date,
                                profit_rate=profit_rate
                            )
            
            # b. 检查买入信号（只在回测期间内）
            if start_date <= trade_date <= end_date:
                if trade_date in signals_by_date:
                    for signal in signals_by_date[trade_date]:
                        stock_code = signal.stock_code
                        
                        # 如果已经持有该股票，跳过
                        if stock_code in portfolio.positions:
                            continue
                        
                        price_data_for_stock = current_prices.get(stock_code, {})
                        should_buy, buy_price = backtest_strategy.should_buy(
                            signal, price_data_for_stock, trade_date
                        )
                        
                        if should_buy:
                            capital_to_invest = initial_capital * capital_per_stock_ratio
                            success = portfolio.buy(
                                stock_code, buy_price, trade_date,
                                capital_to_invest, signal.strategy_type
                            )
                            
                            if success:
                                # 更新策略结果
                                self.strategy_service.update_strategy_result(
                                    stock_code=stock_code,
                                    signal_date=signal.signal_date,
                                    result_type='first_buy',
                                    execution_date=trade_date
                                )
            
            # c. 记录每日资产
            portfolio.record_daily_value(trade_date, current_prices)
        
        # 5. 计算最终指标
        logger.info("=" * 50)
        logger.info("【阶段5】计算回测指标...")
        metrics = self._calculate_metrics(portfolio.history, initial_capital)
        
        # 6. 统计交易
        winning_trades = sum(1 for log in trade_logs if log['profit'] > 0)
        losing_trades = len(trade_logs) - winning_trades
        win_rate = (winning_trades / len(trade_logs)) if trade_logs else 0
        
        logger.info(f"总交易次数: {len(trade_logs)}")
        logger.info(f"盈利次数: {winning_trades}, 亏损次数: {losing_trades}")
        logger.info(f"胜率: {win_rate*100:.2f}%")
        logger.info(f"总收益率: {metrics.get('total_return', 0)*100:.2f}%")
        logger.info(f"最大回撤: {metrics.get('max_drawdown', 0)*100:.2f}%")
        
        # 7. 保存结果
        logger.info("=" * 50)
        logger.info("【阶段6】保存回测结果...")
        portfolio_result = PortfolioBacktest.objects.create(
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            capital_per_stock_ratio=capital_per_stock_ratio,
            final_capital=metrics.get('final_capital', initial_capital),
            total_profit=metrics.get('total_profit', 0),
            total_return=metrics.get('total_return', 0),
            max_drawdown=metrics.get('max_drawdown', 0),
            max_profit=metrics.get('max_profit', 0),
            total_trades=len(trade_logs),
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
        
        logger.info(f"✅ 回测完成! 结果ID: {portfolio_result.id}")
        
        return {
            'status': 'SUCCESS',
            'message': f'回测完成，共{len(trade_logs)}笔交易',
            'result_id': portfolio_result.id,
            'metrics': {
                'total_return': float(metrics.get('total_return', 0)),
                'win_rate': float(win_rate),
                'total_trades': len(trade_logs),
                'max_drawdown': float(metrics.get('max_drawdown', 0)),
            }
        }
    
    def _calculate_metrics(self, history, initial_capital):
        """计算回测指标"""
        if not history:
            return {}
        
        df = pd.DataFrame(history)
        
        final_capital = df['value'].iloc[-1]
        total_profit = final_capital - initial_capital
        total_return = (total_profit / initial_capital) if initial_capital > 0 else 0
        
        # 最大盈利
        max_profit = max(0, df['value'].max() - initial_capital)
        
        # 最大回撤
        peak = df['value'].cummax()
        drawdown = (df['value'] - peak) / peak
        max_drawdown = drawdown.min()
        
        return {
            'final_capital': final_capital,
            'total_profit': total_profit,
            'total_return': total_return,
            'max_profit': max_profit,
            'max_drawdown': max_drawdown,
        }
