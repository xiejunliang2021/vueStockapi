"""
Tushare 数据服务
使用 Tushare API 获取股票日线数据（前复权）
"""
import pandas as pd
import tushare as ts
from datetime import datetime, timedelta, date
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class TushareDataService:
    """Tushare 数据服务类，封装股票数据查询"""
    
    def __init__(self, token: Optional[str] = None):
        """
        初始化 Tushare 服务
        
        Args:
            token: Tushare API token，如果不提供则从环境变量或配置读取
        """
        if token:
            ts.set_token(token)
        
        self.pro = ts.pro_api()
        logger.info("Tushare 数据服务初始化成功")
    
    def get_stock_daily_data(
        self,
        stock_id: str,
        anchor_date: date,
        days_before: int = 100,
        days_after: int = 60
    ) -> Optional[pd.DataFrame]:
        """
        获取指定股票的日线数据（前复权）
        
        Args:
            stock_id: 股票代码（ts_code 格式，如 '000001.SZ'）
            anchor_date: 锚点日期（策略日期）
            days_before: 向前取多少天，默认100天
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
                logger.error(f'日期格式错误: {anchor_date}')
                return None
        
        # 计算时间范围（扩展范围以确保有足够的交易日）
        start_date = anchor_date - timedelta(days=int(days_before * 1.5))  # 扩展1.5倍（考虑非交易日）
        end_date = min(
            anchor_date + timedelta(days=int(days_after * 1.5)),
            datetime.now().date()
        )
        
        # 转换为 Tushare 需要的日期格式 (YYYYMMDD)
        start_date_str = start_date.strftime('%Y%m%d')
        end_date_str = end_date.strftime('%Y%m%d')
        
        logger.info(f'从 Tushare 查询 {stock_id} 数据: {start_date} 至 {end_date}')
        
        try:
            # 调用 Tushare API 获取前复权日线数据
            df = self.pro.daily(
                ts_code=stock_id,
                start_date=start_date_str,
                end_date=end_date_str,
                adj='qfq'  # 前复权
            )
            
            if df is None or df.empty:
                logger.warning(f'未找到 {stock_id} 在 {start_date} 至 {end_date} 的数据')
                return None
            
            # 数据预处理
            df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
            df = df.sort_values('trade_date')
            
            # 重命名列以匹配 Backtrader 格式
            df = df.rename(columns={
                'vol': 'volume'
            })
            
            # 选择需要的列
            df = df[['trade_date', 'open', 'high', 'low', 'close', 'volume']]
            
            # 设置索引
            df.set_index('trade_date', inplace=True)
            
            # 计算涨停标记：(今日收盘 - 昨日收盘) / 昨日收盘 > 0.096
            df['up_limit'] = (
                (df['close'] - df['close'].shift(1)) / df['close'].shift(1) > 0.096
            ).astype(int)
            
            # ✅ 修复：按交易日数量筛选，而非按自然日
            # 找到锚点日期在数据中的位置
            try:
                anchor_idx = df.index.get_loc(pd.Timestamp(anchor_date))
            except KeyError:
                # 如果锚点日期不在数据中，找最接近的日期
                df_reset = df.reset_index()
                df_reset['diff'] = abs((df_reset['trade_date'] - pd.Timestamp(anchor_date)).dt.days)
                anchor_idx = df_reset['diff'].idxmin()
                logger.warning(f'锚点日期 {anchor_date} 不在交易日中，使用最接近的日期')
            
            # 计算实际的筛选范围（按交易日数量）
            start_idx = max(0, anchor_idx - days_before)
            end_idx = min(len(df) - 1, anchor_idx + days_after)
            
            # 按索引筛选（保留足够的交易日）
            df = df.iloc[start_idx:end_idx + 1]
            
            logger.info(f'成功从 Tushare 获取 {len(df)} 条日线数据（前复权）')
            logger.info(f'数据范围: {df.index.min().date()} 至 {df.index.max().date()}')
            return df
            
        except Exception as e:
            logger.error(f'从 Tushare 获取日线数据失败: {e}')
            import traceback
            traceback.print_exc()
            return None
