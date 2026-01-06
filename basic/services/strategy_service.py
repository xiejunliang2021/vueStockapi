"""
策略服务层：封装策略数据访问和业务逻辑
"""
from typing import List, Dict, Optional
from datetime import date, timedelta
from django.db.models import Q
from ..models import PolicyDetails, StockDailyData, Code
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class StrategySignal:
    """策略信号数据传输对象（DTO）"""
    
    def __init__(self, signal_dict):
        self.stock_code = signal_dict['stock_code']
        self.stock_name = signal_dict['stock_name']
        self.signal_date = signal_dict['signal_date']
        self.first_buy_point = Decimal(str(signal_dict['first_buy_point']))
        self.second_buy_point = Decimal(str(signal_dict.get('second_buy_point', 0)))
        self.stop_loss_point = Decimal(str(signal_dict['stop_loss_point']))
        self.take_profit_point = Decimal(str(signal_dict['take_profit_point']))
        self.strategy_type = signal_dict.get('strategy_type', '龙回头')
        self.policy_id = signal_dict.get('policy_id')
        
    def to_dict(self):
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'signal_date': self.signal_date,
            'first_buy_point': float(self.first_buy_point),
            'second_buy_point': float(self.second_buy_point),
            'stop_loss_point': float(self.stop_loss_point),
            'take_profit_point': float(self.take_profit_point),
            'strategy_type': self.strategy_type,
        }


class StrategyService:
    """策略服务类"""
    
    def __init__(self, db_alias='default'):
        self.db_alias = db_alias
    
    def get_signals_for_backtest(
        self,
        start_date: date,
        end_date: date,
        strategy_type: Optional[str] = None,
        stock_codes: Optional[List[str]] = None,
        exclude_st: bool = True,
        exclude_cyb: bool = True
    ) -> List[StrategySignal]:
        """
        获取回测所需的策略信号
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            strategy_type: 策略类型（可选）
            stock_codes: 指定股票代码列表（可选）
            exclude_st: 是否排除ST股票
            exclude_cyb: 是否排除创业板
            
        Returns:
            策略信号列表
        """
        logger.info(f"获取策略信号: {start_date} 到 {end_date}")
        
        # 构建查询条件
        query = Q(date__range=(start_date, end_date))
        
        if strategy_type and strategy_type != '全部':
            query &= Q(strategy_type=strategy_type)
        
        if stock_codes:
            query &= Q(stock__ts_code__in=stock_codes)
        
        # 排除股票
        excluded_codes = set()
        if exclude_st:
            st_codes = Code.objects.filter(name__icontains='ST').values_list('ts_code', flat=True)
            excluded_codes.update(st_codes)
            logger.info(f"排除ST股票: {len(st_codes)}只")
        
        if exclude_cyb:
            cyb_codes = Code.objects.filter(ts_code__startswith='300').values_list('ts_code', flat=True)
            excluded_codes.update(cyb_codes)
            logger.info(f"排除创业板股票: {len(cyb_codes)}只")
        
        if excluded_codes:
            query &= ~Q(stock__ts_code__in=excluded_codes)
        
        # 查询策略详情
        signals_qs = PolicyDetails.objects.using(self.db_alias).filter(query)\
            .select_related('stock')\
            .order_by('date')
        
        signal_count = signals_qs.count()
        logger.info(f"找到 {signal_count} 个策略信号")
        
        # 转换为DTO
        signals = []
        for policy in signals_qs:
            signal_dict = {
                'stock_code': policy.stock.ts_code,
                'stock_name': policy.stock.name,
                'signal_date': policy.date,
                'first_buy_point': policy.first_buy_point,
                'second_buy_point': policy.second_buy_point or 0,
                'stop_loss_point': policy.stop_loss_point,
                'take_profit_point': policy.take_profit_point,
                'strategy_type': policy.strategy_type,
                'policy_id': policy.id,
            }
            signals.append(StrategySignal(signal_dict))
        
        return signals
    
    def get_price_data(
        self,
        stock_codes: List[str],
        start_date: date,
        end_date: date
    ) -> Dict[date, Dict[str, Dict]]:
        """
        获取指定股票在指定时间范围的价格数据
        
        Returns:
            {date: {stock_code: {'close': price, 'high': price, 'low': price}}}
        """
        logger.info(f"获取 {len(stock_codes)} 只股票的价格数据")
        
        daily_data = StockDailyData.objects.filter(
            stock__ts_code__in=stock_codes,
            trade_date__range=(start_date, end_date)
        ).values('trade_date', 'stock__ts_code', 'close', 'high', 'low')
        
        # 转换为嵌套字典
        price_map = {}
        record_count = 0
        for record in daily_data:
            trade_date = record['trade_date']
            stock_code = record['stock__ts_code']
            
            if trade_date not in price_map:
                price_map[trade_date] = {}
            
            price_map[trade_date][stock_code] = {
                'close': float(record['close']),
                'high': float(record['high']),
                'low': float(record['low']),
            }
            record_count += 1
        
        logger.info(f"获取到 {record_count} 条价格记录，覆盖 {len(price_map)} 个交易日")
        return price_map
    
    def update_strategy_result(
        self,
        stock_code: str,
        signal_date: date,
        result_type: str,
        execution_date: date,
        profit_rate: Optional[float] = None
    ):
        """
        更新策略执行结果
        
        Args:
            stock_code: 股票代码
            signal_date: 信号日期
            result_type: 结果类型 ('first_buy', 'second_buy', 'take_profit', 'stop_loss', 'timeout')
            execution_date: 执行日期
            profit_rate: 盈利率
        """
        try:
            # 尝试获取并更新策略
            from django.db import connection
            
            # 确保Oracle连接是活跃的
            if self.db_alias == 'default':
                try:
                    connection.ensure_connection()
                except Exception as conn_err:
                    logger.warning(f"数据库连接检查失败，尝试重连: {conn_err}")
                    connection.close()
                    connection.connect()
            
            policy = PolicyDetails.objects.using(self.db_alias).get(
                stock__ts_code=stock_code,
                date=signal_date
            )
            
            # 更新对应的执行时间
            if result_type == 'first_buy':
                policy.first_buy_time = execution_date
                logger.info(f"更新策略 {stock_code} 第一买点时间: {execution_date}")
            elif result_type == 'second_buy':
                policy.second_buy_time = execution_date
                logger.info(f"更新策略 {stock_code} 第二买点时间: {execution_date}")
            elif result_type == 'take_profit':
                policy.take_profit_time = execution_date
                policy.current_status = 'S'
                logger.info(f"更新策略 {stock_code} 止盈时间: {execution_date}")
            elif result_type in ['stop_loss', 'timeout']:
                if result_type == 'stop_loss':
                    policy.stop_loss_time = execution_date
                policy.current_status = 'F'
                logger.info(f"更新策略 {stock_code} 止损/超时: {execution_date}")
            
            # 更新盈利情况
            if profit_rate is not None:
                policy.holding_profit = Decimal(str(profit_rate * 100))
            
            policy.save()
            
        except PolicyDetails.DoesNotExist:
            logger.warning(f"策略不存在: {stock_code} @ {signal_date}")
        except Exception as e:
            # 数据库连接错误不应该中断回测
            logger.error(f"更新策略结果失败: {e}")
            if 'not connected' in str(e).lower():
                logger.error("数据库连接已断开，跳过策略状态更新")
            # 不抛出异常，让回测继续
