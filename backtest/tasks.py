from celery import shared_task
import logging
from datetime import datetime
from decimal import Decimal
import traceback

from .services.backtest_service import BacktestService
from .services.backtrader_service import BacktraderBacktestService
from utils.telegram import send_telegram_message


logger = logging.getLogger(__name__)


@shared_task(bind=True)
def run_portfolio_backtest(self, filters, backtest_params):
    """
    执行组合回测任务
    
    Args:
        filters: 回测过滤条件
            - strategy_name: 策略名称
            - strategy_type: 策略类型（可选，默认'龙回头'）
            - start_date: 开始日期（字符串格式'YYYY-MM-DD'）
            - end_date: 结束日期（字符串格式'YYYY-MM-DD'）
        backtest_params: 回测参数
            - total_capital: 初始资金
            - capital_per_stock_ratio: 单票资金占比
            - hold_timeout_days: 最大持仓天数
            - db_alias: 数据库别名
            - use_backtrader: 是否使用Backtrader引擎（默认False）
            - commission: 佣金率（仅Backtrader，默认0.0003）
    
    Returns:
        回测结果字典
    """
    try:
        logger.info("="*60)
        logger.info("🚀 回测任务开始")
        logger.info("="*60)
        
        # 解构参数
        strategy_name = filters['strategy_name']
        
        # 处理日期参数（支持字符串和date对象）
        start_date = filters['start_date']
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        end_date = filters['end_date']
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        initial_capital = Decimal(str(backtest_params['total_capital']))
        capital_per_stock_ratio = Decimal(str(backtest_params['capital_per_stock_ratio']))
        hold_timeout_days = backtest_params['hold_timeout_days']
        db_alias = backtest_params.get('db_alias', 'default')
        strategy_type = filters.get('strategy_type', '龙回头')
        
        # 选择回测引擎
        use_backtrader = backtest_params.get('use_backtrader', False)
        engine_name = 'Backtrader' if use_backtrader else '自定义引擎'
        
        logger.info(f"回测引擎: {engine_name}")
        logger.info(f"策略名称: {strategy_name}")
        logger.info(f"策略类型: {strategy_type}")
        logger.info(f"回测区间: {start_date} ~ {end_date}")
        logger.info(f"初始资金: {initial_capital:,.2f}")
        logger.info(f"单票比例: {capital_per_stock_ratio*100:.1f}%")
        logger.info(f"最大持仓: {hold_timeout_days}天")
        
        # 使用对应的服务层执行回测
        if use_backtrader:
            backtest_service = BacktraderBacktestService()
            commission = backtest_params.get('commission', 0.0003)
            logger.info(f"佣金率: {commission*100:.2f}%")
            
            # 根据策略类型选择对应的回测方法
            if strategy_type == '连续涨停':
                # 使用连续涨停策略回测（LimitBreakStrategy）
                logger.info("📊 使用连续涨停策略 (LimitBreakStrategy)")
                
                # 数据源选择：默认 Tushare，可通过参数指定
                data_source = backtest_params.get('data_source', 'tushare')
                logger.info(f"数据源: {data_source.upper()}")
                
                result = backtest_service.run_limit_break_backtest(
                    strategy_name=strategy_name,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=initial_capital,
                    stock_ids=None,  # 查询所有L状态股票
                    profit_target=backtest_params.get('profit_target', 0.10),  # 获取止盈参数
                    stop_loss=backtest_params.get('stop_loss', 0.05),          # 获取止损参数
                    max_hold_days=backtest_params.get('hold_timeout_days', 30), # 获取最大持仓天数
                    lookback_days=20,
                    max_wait_days=100,
                    position_pct=float(capital_per_stock_ratio),
                    commission=commission,
                    db_alias=db_alias,
                    data_source=data_source  # ✅ 传递数据源参数
                )
            else:
                # 使用龙回头策略回测（DragonTurnBacktraderStrategy）
                logger.info("🐉 使用龙回头策略 (DragonTurnBacktraderStrategy)")
                result = backtest_service.run_backtest(
                    strategy_name=strategy_name,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=initial_capital,
                    capital_per_stock_ratio=capital_per_stock_ratio,
                    strategy_type=strategy_type,
                    hold_timeout_days=hold_timeout_days,
                    db_alias=db_alias,
                    commission=commission
                )
        else:
            backtest_service = BacktestService()
            
            result = backtest_service.run_backtest(
                strategy_name=strategy_name,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                capital_per_stock_ratio=capital_per_stock_ratio,
                strategy_type=strategy_type,
                hold_timeout_days=hold_timeout_days,
                db_alias=db_alias
            )
        
        logger.info("="*60)
        logger.info(f"✅ 回测任务完成 ({engine_name})")
        logger.info("="*60)
        
        # 发送 Telegram 通知
        try:
            status_icon = "✅" if result.get('status') == 'SUCCESS' else "⚠️"
            msg = f"{status_icon} **回测任务执行完毕** ({engine_name})\n"
            msg += f"策略: {strategy_name} ({strategy_type})\n"
            msg += f"区间: {start_date} ~ {end_date}\n"
            
            if result.get('status') == 'SUCCESS':
                total_return = float(result.get('total_return', 0)) * 100
                trade_count = len(result.get('trades', []))
                msg += f"状态: 成功\n"
                msg += f"总收益率: {total_return:.2f}%\n"
                msg += f"交易次数: {trade_count}次\n"
            else:
                msg += f"状态: {result.get('status', '未知')}\n"
                msg += f"信息: {result.get('message', '无详细信息')}\n"
            
            send_telegram_message(msg)
        except Exception as tg_e:
            logger.error(f"发送 Telegram 通知报错: {tg_e}")
        
        return result
        
    except Exception as e:
        error_msg = f"回测任务失败: {str(e)}\n{traceback.format_exc()}"
        logger.error("="*60)
        logger.error("❌ 回测任务失败")
        logger.error(error_msg)
        logger.error("="*60)
        
        # 发送错误通知到 Telegram
        try:
            msg = f"❌ **回测任务异常崩溃**\n错误: {str(e)}"
            send_telegram_message(msg)
        except Exception as tg_e:
            logger.error(f"发送 Telegram 错误通知失败: {tg_e}")
            
        return {'status': 'FAILURE', 'error': error_msg}
