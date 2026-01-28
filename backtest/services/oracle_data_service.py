"""
Oracle 数据服务
使用 Django ORM 从 Oracle 数据库查询股票数据
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional
import logging

from basic.models import Code, StockDailyData, PolicyDetails

logger = logging.getLogger(__name__)


class OracleDataService:
    """Oracle 数据服务类，封装股票数据查询"""
    
    def __init__(self, db_alias='default'):
        """
        初始化数据服务
        
        Args:
            db_alias: 数据库别名，默认为 'default' (Oracle)
        """
        self.db_alias = db_alias
    
    def get_strategy_stocks(
        self, 
        strategy_type: str = 'L',
        current_status: str = 'L',
        limit: Optional[int] = None
    ) -> List[dict]:
        """
        获取策略相关股票列表
        
        Args:
            strategy_type: 策略类型，默认 'L' (龙回头)
            current_status: 当前状态，默认 'L' (进行中)
            limit: 限制返回数量
            
        Returns:
            股票列表，每项包含: id, stock_name, strategy_type, stock_id, date
        """
        logger.info(f"查询策略股票: strategy_type={strategy_type}, status={current_status}")
        
        query = PolicyDetails.objects.using(self.db_alias).filter(
            current_status=current_status
        )
        
        # 如果指定了策略类型（非 'L' 的情况是指连续涨停等其他策略）
        if strategy_type and strategy_type != 'L':
            query = query.filter(strategy_type=strategy_type)
        
        query = query.select_related('stock').order_by('-id')
        
        if limit:
            query = query[:limit]
        
        stocks = []
        for policy in query:
            stocks.append({
                'id': policy.id,
                'stock_name': policy.stock.name,
                'strategy_type': policy.strategy_type,
                'stock_id': policy.stock.ts_code,
                'date': policy.date,
            })
        
        logger.info(f"找到 {len(stocks)} 只股票")
        return stocks
    
    def get_strategy_stocks_by_date_range(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        limit: Optional[int] = None
    ) -> List[dict]:
        """
        根据日期范围获取策略相关股票列表（不限制策略类型和状态）
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            limit: 限制返回数量
            
        Returns:
            股票列表，每项包含: id, stock_name, strategy_type, stock_id, date
        """
        logger.info(f"查询策略股票: date_range={start_date}~{end_date}")
        
        query = PolicyDetails.objects.using(self.db_alias).filter(
            date__gte=start_date,
            date__lte=end_date
        )
        
        query = query.select_related('stock').order_by('date')  # 按日期升序
        
        if limit:
            query = query[:limit]
        
        stocks = []
        for policy in query:
            stocks.append({
                'id': policy.id,
                'stock_name': policy.stock.name,
                'strategy_type': policy.strategy_type,
                'stock_id': policy.stock.ts_code,
                'date': policy.date,  # 这个日期将作为锚点
            })
        
        logger.info(f"在日期范围 {start_date}~{end_date} 找到 {len(stocks)} 只股票")
        return stocks
    
    def get_stock_daily_data(
        self,
        stock_id: str,
        anchor_date: datetime.date,
        days_before: int = 60,
        days_after: int = 60
    ) -> Optional[pd.DataFrame]:
        """
        获取指定股票的日线数据
        
        Args:
            stock_id: 股票代码（ts_code）
            anchor_date: 锚点日期（策略日期）
            days_before: 向前取多少天，默认60天
            days_after: 向后取多少天，默认60天
            
        Returns:
            pandas DataFrame，包含以下列:
            - trade_date (索引)
            - open, high, low, close, volume
            - up_limit (计算得出的涨停标记：1=涨停，0=非涨停)
        """
        # 日期处理
        if isinstance(anchor_date, datetime):
            anchor_date = anchor_date.date()
        elif isinstance(anchor_date, str):
            try:
                anchor_date = datetime.strptime(anchor_date, '%Y-%m-%d').date()
            except ValueError:
                try:
                    anchor_date = datetime.strptime(anchor_date, '%Y-%m-%d %H:%M:%S').date()
                except ValueError:
                    logger.error(f'日期格式错误: {anchor_date}')
                    return None
        
        # 计算时间范围
        start_date = anchor_date - timedelta(days=days_before)
        end_date = min(
            anchor_date + timedelta(days=days_after),
            datetime.now().date()
        )
        
        logger.debug(f'查询 {stock_id} 数据: {start_date} 至 {end_date}')
        
        try:
            # 使用 Django ORM 查询
            daily_data = StockDailyData.objects.using(self.db_alias).filter(
                stock__ts_code=stock_id,
                trade_date__gte=start_date,
                trade_date__lte=end_date
            ).order_by('trade_date').values(
                'trade_date', 'open', 'high', 'low', 'close', 'volume'
            )
            
            if not daily_data:
                logger.warning(f'未找到 {stock_id} 在 {start_date} 至 {end_date} 的数据')
                return None
            
            # 转换为 DataFrame
            df = pd.DataFrame(list(daily_data))
            
            # 转换数据类型
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            for col in ['open', 'high', 'low', 'close']:
                df[col] = df[col].astype(float)
            df['volume'] = df['volume'].astype(int)
            
            # 设置索引
            df.set_index('trade_date', inplace=True)
            
            # 计算涨停标记：(今日收盘 - 昨日收盘) / 昨日收盘 > 0.096
            df['up_limit'] = (
                (df['close'] - df['close'].shift(1)) / df['close'].shift(1) > 0.096
            ).astype(int)
            
            logger.debug(f'成功获取 {len(df)} 条日线数据')
            return df
            
        except Exception as e:
            logger.error(f'获取日线数据失败: {e}')
            import traceback
            traceback.print_exc()
            return None
    
    def get_stock_info(self, stock_id: str) -> Optional[dict]:
        """
        获取股票基本信息
        
        Args:
            stock_id: 股票代码
            
        Returns:
            股票信息字典: {ts_code, symbol, name, area, industry, market}
        """
        try:
            code = Code.objects.using(self.db_alias).get(ts_code=stock_id)
            return {
                'ts_code': code.ts_code,
                'symbol': code.symbol,
                'name': code.name,
                'area': code.area,
                'industry': code.industry,
                'market': code.market,
            }
        except Code.DoesNotExist:
            logger.warning(f'股票代码不存在: {stock_id}')
            return None
        except Exception as e:
            logger.error(f'查询股票信息失败: {e}')
            return None
