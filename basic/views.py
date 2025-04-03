from rest_framework import generics
from .models import PolicyDetails, Code, TradingCalendar, StockDailyData, StrategyStats
from .serializers import PolicyDetailsSerializer, CodeSerializer, TradingCalendarSerializer, StockPatternAnalysisSerializer, StockPatternResultSerializer, StrategyStatsSerializer
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .analysis import ContinuousLimitStrategy
from datetime import datetime
from .utils import StockDataFetcher
from django.db import models
from django.db.models import Min, Max, Avg, Count

class PolicyDetailsListCreateView(generics.ListCreateAPIView):
    """策略详情列表和创建视图"""
    queryset = PolicyDetails.objects.all()
    serializer_class = PolicyDetailsSerializer
    # 添加过滤字段
    filterset_fields = ['stock', 'date', 'strategy_type']


class CodeListCreateView(generics.ListCreateAPIView):
    """股票代码列表和创建视图"""
    queryset = Code.objects.all()
    serializer_class = CodeSerializer
    # 添加过滤字段
    filterset_fields = ['ts_code', 'name', 'industry', 'symbol']

class CodeRetrieveUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    """股票代码详情、更新和删除视图"""
    queryset = Code.objects.all()
    serializer_class = CodeSerializer
    lookup_field = 'ts_code'

class ManualStrategyAnalysisView(APIView):
    """手动策略分析视图"""
    
    def analyze_signals(self, start_date, end_date, stock_code=None):
        """分析策略信号
        
        策略逻辑：
        1. 获取所有状态为"进行中"的策略记录
        2. 对每个策略记录：
           a. 获取策略生成日期之后的日线数据
           b. 从第一买点时间开始，检查后续100个交易日内：
              - 如果期间最低价没有触及第二买点，且出现止盈 -> 第一买点成功
              - 如果期间最低价触及第二买点但未触及止损，且出现7.5%涨幅 -> 第二买点成功
              - 如果期间最低价触及止损价 -> 失败
           
        统计指标：
        - 成功率统计
        - 平均持仓时间
        - 最大回撤
        - 盈利分布
        """
        try:
            # 使用聚合查询获取数据统计
            data_stats = StockDailyData.objects.filter(
                trade_date__range=[start_date, end_date]
            ).aggregate(
                min_records=Min('id'),
                max_records=Max('id'),
                avg_records=Avg('id'),
                total_records=Count('id')
            )
            
            # 初始化统计指标
            stats = {
                'first_buy_success': 0,   # 第一买点成功次数
                'second_buy_success': 0,  # 第二买点成功次数
                'failed': 0,              # 失败次数
                'total': 0,               # 总信号数
                'avg_hold_days': 0,       # 平均持仓天数
                'max_drawdown': 0,        # 最大回撤
                'profit_distribution': {   # 盈利分布
                    '0-3%': 0,
                    '3-5%': 0,
                    '5-7%': 0,
                    '7-10%': 0,
                    '>10%': 0
                },
                'total_hold_days': 0,     # 总持仓天数（用于计算平均值）
                'analyzed_stocks': 0,     # 用于统计分析的股票数量
                'avg_records_per_stock': 0, # 平均每个股票的日线数据记录数
            }
            
            # 初始化查询集
            signals_query = PolicyDetails.objects.filter(
                current_status='L'  # 只分析进行中的信号
            ).select_related('stock')
            
            # 如果提供了股票代码，进行过滤
            if stock_code:
                print(f"Filtering signals for stock: {stock_code}")
                signals_query = signals_query.filter(stock__ts_code=stock_code)
            
            # 如果提供了日期范围，进行过滤
            if start_date and end_date:
                signals_query = signals_query.filter(date__range=[start_date, end_date])
            
            # 添加日志
            print(f"Analyzing signals for date range: {start_date} to {end_date}")
            print(f"Initial query count: {signals_query.count()}")
            
            # 验证是否有数据可分析
            if not signals_query.exists():
                print("No signals found for analysis")
                return {
                    'first_buy_success': 0,
                    'second_buy_success': 0,
                    'failed': 0,
                    'total': 0,
                    'avg_hold_days': 0,
                    'max_drawdown': 0,
                    'profit_distribution': {
                        '0-3%': 0, '3-5%': 0, '5-7%': 0,
                        '7-10%': 0, '>10%': 0
                    },
                    'total_hold_days': 0,
                    'analyzed_stocks': 0,
                    'avg_records_per_stock': 0
                }
            
            # 添加分析结果统计
            analyzed_stocks = set()  # 用于统计分析的股票数量
            
            # 遍历每个策略记录
            for signal in signals_query:
                analyzed_stocks.add(signal.stock.ts_code)
                print(f"Processing signal for stock: {signal.stock.ts_code}")
                
                stats['total'] += 1
                
                # 获取该股票在策略生成日期之后的所有日线数据
                daily_data = StockDailyData.objects.filter(
                    stock=signal.stock,
                    trade_date__gt=signal.date,
                    trade_date__lte=end_date
                ).order_by('trade_date')
                
                daily_data_count = daily_data.count()
                print(f"Found {daily_data_count} daily records for {signal.stock.ts_code}")
                
                if daily_data_count < 3:
                    print(f"Insufficient data for {signal.stock.ts_code}, skipping...")
                    continue
                
                # 获取策略参数
                first_buy_point = float(signal.first_buy_point)
                second_buy_point = float(signal.second_buy_point) if signal.second_buy_point else first_buy_point * 0.9
                stop_loss_point = float(signal.stop_loss_point)
                
                first_buy_triggered = False
                second_buy_triggered = False
                first_buy_date = None
                second_buy_date = None
                max_price = 0
                min_price = float('inf')
                hold_days = 0
                consecutive_stop_loss_days = 0  # 连续跌破止损价的天数
                
                # 分析每一天的数据
                for day_data in daily_data:
                    low_price = float(day_data.low)
                    high_price = float(day_data.high)
                    close_price = float(day_data.close)
                    
                    # 更新最大最小价格（用于计算回撤）
                    max_price = max(max_price, high_price)
                    min_price = min(min_price, low_price)
                    
                    # 第一次触及买点一时开始买入
                    if not first_buy_triggered and low_price <= first_buy_point:
                        first_buy_triggered = True
                        first_buy_date = day_data.trade_date
                        signal.first_buy_time = first_buy_date
                        signal.save()
                        continue
                    
                    # 只有在触发第一买点后才进行后续判断
                    if first_buy_triggered:
                        hold_days = (day_data.trade_date - first_buy_date).days
                        
                        # 只分析100个交易日内的数据
                        if hold_days > 100:
                            signal.current_status = 'F'
                            signal.stop_loss_time = day_data.trade_date
                            signal.holding_price = stop_loss_point
                            signal.save()
                            stats['failed'] += 1
                            stats['total_hold_days'] += hold_days
                            break
                        
                        # 情况1：最高价达到买点一的1.075倍
                        target_price_1 = first_buy_point * 1.075
                        if high_price >= target_price_1:
                            # 检查在达到最高价之前的最低价是否都大于买点二
                            previous_data = daily_data.filter(
                                trade_date__gte=first_buy_date,
                                trade_date__lt=day_data.trade_date
                            )
                            if all(float(d.low) > second_buy_point for d in previous_data):
                                signal.current_status = 'S'
                                signal.take_profit_time = day_data.trade_date
                                signal.holding_price = first_buy_point
                                signal.save()
                                
                                stats['first_buy_success'] += 1
                                stats['total_hold_days'] += hold_days
                                profit_rate = round((high_price - first_buy_point) / first_buy_point * 100, 2)
                                self._update_profit_distribution(stats, profit_rate)
                                break
                        
                        # 情况2和3：价格触及买点二
                        if low_price <= second_buy_point and not second_buy_triggered:
                            second_buy_triggered = True
                            second_buy_date = day_data.trade_date
                            signal.second_buy_time = second_buy_date
                            avg_price = round((first_buy_point + second_buy_point) / 2, 2)
                            target_price_2 = avg_price * 1.075
                            
                            # 检查是否触及止损价
                            if low_price <= stop_loss_point:
                                consecutive_stop_loss_days = 1
                            
                            # 检查在触及买点二之后的数据
                            subsequent_data = daily_data.filter(
                                trade_date__gt=day_data.trade_date
                            ).order_by('trade_date')
                            
                            for next_day in subsequent_data:
                                next_low = float(next_day.low)
                                next_high = float(next_day.high)
                                next_close = float(next_day.close)
                                
                                # 检查是否连续跌破止损价
                                if next_close <= stop_loss_point:
                                    consecutive_stop_loss_days += 1
                                else:
                                    consecutive_stop_loss_days = 0
                                
                                # 情况3：连续三天收盘价跌破止损价
                                if consecutive_stop_loss_days >= 3:
                                    signal.current_status = 'F'
                                    signal.stop_loss_time = next_day.trade_date
                                    signal.holding_price = stop_loss_point
                                    signal.save()
                                    
                                    stats['failed'] += 1
                                    stats['total_hold_days'] += (next_day.trade_date - second_buy_date).days
                                    break
                                
                                # 情况2：达到目标价格且未触及止损
                                if next_high >= target_price_2 and consecutive_stop_loss_days == 0:
                                    signal.current_status = 'S'
                                    signal.take_profit_time = next_day.trade_date
                                    signal.holding_price = avg_price
                                    signal.save()
                                    
                                    stats['second_buy_success'] += 1
                                    stats['total_hold_days'] += (next_day.trade_date - second_buy_date).days
                                    profit_rate = round((next_high - avg_price) / avg_price * 100, 2)
                                    self._update_profit_distribution(stats, profit_rate)
                                    break
                            
                            if signal.current_status in ['S', 'F']:
                                break
            
            # 计算最大回撤
            if max_price > 0 and min_price < float('inf'):
                drawdown = round((max_price - min_price) / max_price * 100, 2)
                stats['max_drawdown'] = max(stats['max_drawdown'], drawdown)
            
            # 计算平均持仓天数
            if stats['total'] > 0:
                stats['avg_hold_days'] = round(stats['total_hold_days'] / stats['total'], 2)
            
            # 更新返回的统计信息
            stats.update({
                'analyzed_stocks': len(analyzed_stocks),
                'avg_records_per_stock': round(sum(
                    daily_data.count() for signal in signals_query
                ) / len(analyzed_stocks), 2) if analyzed_stocks else 0,
                'data_stats': data_stats  # 添加数据统计信息
            })
            
            return stats
            
        except Exception as e:
            raise Exception(f"策略分析失败: {str(e)}")
    
    def _update_profit_distribution(self, stats, profit_rate):
        """更新盈利分布统计
        
        Args:
            stats: 统计数据字典
            profit_rate: 盈利率（百分比）
        """
        if profit_rate <= 3:
            stats['profit_distribution']['0-3%'] += 1
        elif profit_rate <= 5:
            stats['profit_distribution']['3-5%'] += 1
        elif profit_rate <= 7:
            stats['profit_distribution']['5-7%'] += 1
        elif profit_rate <= 10:
            stats['profit_distribution']['7-10%'] += 1
        else:
            stats['profit_distribution']['>10%'] += 1

    def _save_stats(self, stats, end_date, stock_code=None):
        """保存策略统计结果
        
        Args:
            stats: 统计结果字典
            end_date: 统计结束日期
            stock_code: 可选的股票代码
        """
        try:
            # 如果提供了股票代码，获取股票对象
            stock = None
            if stock_code:
                stock = Code.objects.get(ts_code=stock_code)
            
            # 计算成功率
            total_success = stats['first_buy_success'] + stats['second_buy_success']
            success_rate = round((total_success / stats['total'] * 100), 2) if stats['total'] > 0 else 0.00
            
            # 创建统计记录
            StrategyStats.objects.create(
                date=end_date,
                stock=stock,
                total_signals=stats['total'],
                first_buy_success=stats['first_buy_success'],
                second_buy_success=stats['second_buy_success'],
                failed_signals=stats['failed'],
                success_rate=success_rate,
                avg_hold_days=stats['avg_hold_days'],
                max_drawdown=stats['max_drawdown'],
                profit_0_3=stats['profit_distribution']['0-3%'],
                profit_3_5=stats['profit_distribution']['3-5%'],
                profit_5_7=stats['profit_distribution']['5-7%'],
                profit_7_10=stats['profit_distribution']['7-10%'],
                profit_above_10=stats['profit_distribution']['>10%']
            )
            
            return True
        except Exception as e:
            print(f"保存统计数据失败: {str(e)}")
            return False
    
    def post(self, request):
        try:
            start_date = request.data.get('start_date')
            end_date = request.data.get('end_date')
            stock_code = request.data.get('stock_code')  # 可选参数

            # 验证日期格式
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': '日期格式无效，请使用 YYYY-MM-DD 格式'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 分析策略
            stats = self.analyze_signals(start_date, end_date, stock_code)
            
            # 保存统计结果
            stats_saved = self._save_stats(stats, end_date, stock_code)
            
            # 计算成功率
            total_signals = stats['total']
            total_success = stats['first_buy_success'] + stats['second_buy_success']
            success_rate = (total_success / total_signals * 100) if total_signals > 0 else 0
            
            return Response({
                'status': 'success',
                'message': '策略分析完成' + (' 并保存统计数据' if stats_saved else ''),
                'data': {
                    'total_signals': total_signals,
                    'first_buy_success': stats['first_buy_success'],
                    'second_buy_success': stats['second_buy_success'],
                    'failed': stats['failed'],
                    'success_rate': f"{success_rate:.2f}%",
                    'stats_saved': stats_saved
                }
            })

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TradingCalendarListCreateView(generics.ListCreateAPIView):
    """交易日历列表和创建视图"""
    queryset = TradingCalendar.objects.all()
    serializer_class = TradingCalendarSerializer
    filterset_fields = ['date', 'is_trading_day']

    def post(self, request, *args, **kwargs):
        date_str = request.data.get('date')
        if date_str:
            fetcher = StockDataFetcher()
            success = fetcher.update_trading_calendar(date_str)
            if success:
                return Response({'message': '交易日历数据更新成功'})
            return Response(
                {'error': '获取交易日历数据失败'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        return super().post(request, *args, **kwargs)

class TradingCalendarDetailView(generics.RetrieveUpdateDestroyAPIView):
    """交易日历详情、更新和删除视图"""
    queryset = TradingCalendar.objects.all()
    serializer_class = TradingCalendarSerializer
    lookup_field = 'date'

class CheckTradingDayView(generics.GenericAPIView):
    """检查指定日期是否为交易日"""
    
    def get(self, request):
        date_str = request.query_params.get('date')
        
        try:
            if date_str:
                check_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                check_date = datetime.now().date()
            
            # 先查询数据库
            trading_day = TradingCalendar.objects.filter(date=check_date).first()
            
            # 如果没有找到数据，从Tushare获取并保存
            if not trading_day:
                fetcher = StockDataFetcher()
                success = fetcher.update_trading_calendar(date_str)
                if success:
                    trading_day = TradingCalendar.objects.filter(date=check_date).first()
            
            if trading_day:
                return Response({
                    'date': check_date,
                    'is_trading_day': trading_day.is_trading_day,
                    'remark': trading_day.remark
                })
            else:
                return Response({
                    'date': check_date,
                    'is_trading_day': False,
                    'remark': '获取交易日历数据失败'
                })
                
        except ValueError:
            return Response(
                {'error': '日期格式无效，请使用 YYYY-MM-DD 格式'},
                status=status.HTTP_400_BAD_REQUEST
            )

class StockDailyDataUpdateView(APIView):
    http_method_names = ['get', 'post']
    
    """股票日线数据更新和查询视图
    
    GET 请求支持以下查询方式：
    1. 无参数 - 返回最近一个交易日的数据
    2. trade_date - 返回指定日期的数据
    3. start_date + end_date - 返回日期范围内的数据
    4. 仅 start_date - 返回从起始日期到最新的数据
    
    POST 请求支持以下更新方式：
    1. trade_date - 更新指定日期的数据
    2. start_date + end_date - 更新日期范围内的数据
    3. 仅 start_date - 更新从起始日期到最新的数据
    """
    
    def get(self, request):
        try:
            # 获取查询参数
            trade_date = request.query_params.get('trade_date')
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            stock_code = request.query_params.get('stock_code')  # 可选的股票代码过滤
            
            # 初始化查询集
            queryset = StockDailyData.objects.all().select_related('stock')
            
            # 根据不同参数组合进行过滤
            if trade_date:
                try:
                    query_date = datetime.strptime(trade_date, '%Y-%m-%d').date()
                    queryset = queryset.filter(trade_date=query_date)
                except ValueError:
                    return Response(
                        {'status': 'error', 'message': 'trade_date 格式无效，请使用 YYYY-MM-DD 格式'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            elif start_date:
                try:
                    start = datetime.strptime(start_date, '%Y-%m-%d').date()
                    if end_date:
                        end = datetime.strptime(end_date, '%Y-%m-%d').date()
                        if start > end:
                            return Response(
                                {'status': 'error', 'message': 'start_date 不能晚于 end_date'},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        queryset = queryset.filter(trade_date__range=[start, end])
                    else:
                        end = datetime.now().date()
                        queryset = queryset.filter(trade_date__range=[start, end])
                except ValueError:
                    return Response(
                        {'status': 'error', 'message': '日期格式无效，请使用 YYYY-MM-DD 格式'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                # 如果没有提供任何日期参数，返回最近一个交易日的数据
                latest_date = StockDailyData.objects.order_by('-trade_date').values('trade_date').first()
                if latest_date:
                    queryset = queryset.filter(trade_date=latest_date['trade_date'])
                else:
                    return Response({
                        'status': 'success',
                        'message': '数据库中没有数据',
                        'data': []
                    })
            
            # 如果提供了股票代码，进行过滤
            if stock_code:
                queryset = queryset.filter(stock__ts_code=stock_code)
            
            # 按日期和股票代码排序
            queryset = queryset.order_by('-trade_date', 'stock__ts_code')
            
            # 构造返回数据
            data = []
            for record in queryset:
                data.append({
                    'stock_code': record.stock.ts_code,
                    'stock_name': record.stock.name,
                    'trade_date': record.trade_date,
                    'open': float(record.open),
                    'high': float(record.high),
                    'low': float(record.low),
                    'close': float(record.close),
                    'volume': record.volume,
                    'amount': float(record.amount),
                    'up_limit': float(record.up_limit),
                    'down_limit': float(record.down_limit)
                })
            
            return Response({
                'status': 'success',
                'message': f'找到 {len(data)} 条日线数据记录',
                'data': data
            })
            
        except Exception as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request):
        try:
            trade_date = request.data.get('trade_date')
            start_date = request.data.get('start_date')
            end_date = request.data.get('end_date')
            
            # 获取数据
            fetcher = StockDataFetcher()
            
            # 初始化 total_saved
            total_saved = 0
            
            if trade_date:
                result = fetcher.update_all_stocks_daily_data(trade_date=trade_date)
            else:
                result = fetcher.update_all_stocks_daily_data(
                    start_date=start_date,
                    end_date=end_date
                )
            
            # 从结果中获取 total_saved
            if isinstance(result, dict):
                total_saved = result.get('total_saved', 0)
            
            # 根据结果状态返回不同的响应
            if result.get('status') == 'success':
                return Response({
                    'status': 'success',
                    'message': result.get('message', '数据更新成功'),
                    'total_saved': total_saved
                })
            elif result.get('status') == 'skipped':
                return Response({
                    'status': 'skipped',
                    'message': result.get('message', '数据已存在，跳过更新')
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'status': 'failed',
                    'message': result.get('message', '更新失败')
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response(
                {
                    'status': 'error',
                    'message': '更新数据失败',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class StockPatternView(APIView):
    http_method_names = ['get', 'post']
    
    """股票模式分析和查询视图
    
    GET 请求支持以下查询方式：
    1. 无参数 - 返回所有数据
    2. trade_date - 返回指定日期的数据
    3. start_date + end_date - 返回日期范围内的数据
    4. 仅 start_date - 返回从起始日期到最新的数据
    
    POST 请求支持以下分析方式：
    1. trade_date - 分析指定日期的数据
    2. start_date + end_date - 分析日期范围内的数据
    3. 仅 start_date - 分析从起始日期到最新的数据
    """
    
    def get(self, request):
        try:
            # 获取查询参数
            trade_date = request.query_params.get('trade_date')
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            
            # 初始化查询集
            queryset = (PolicyDetails.objects
                .select_related('stock')
                .only('date', 'first_buy_point', 'second_buy_point', 
                      'stop_loss_point', 'take_profit_point', 
                      'strategy_type', 'signal_strength', 'current_status',
                      'first_buy_time', 'second_buy_time', 'take_profit_time',
                      'stop_loss_time')
                .order_by('-date'))
            
            # 根据不同参数组合进行过滤
            if trade_date:
                try:
                    query_date = datetime.strptime(trade_date, '%Y-%m-%d').date()
                    queryset = queryset.filter(date=query_date)
                except ValueError:
                    return Response(
                        {'status': 'error', 'message': 'trade_date 格式无效，请使用 YYYY-MM-DD 格式'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            elif start_date:
                try:
                    start = datetime.strptime(start_date, '%Y-%m-%d').date()
                    if end_date:
                        # 有结束日期，查询日期范围
                        end = datetime.strptime(end_date, '%Y-%m-%d').date()
                        if start > end:
                            return Response(
                                {'status': 'error', 'message': 'start_date 不能晚于 end_date'},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        queryset = queryset.filter(date__range=[start, end])
                    else:
                        # 无结束日期，查询从起始日期到最新
                        queryset = queryset.filter(date__gte=start)
                except ValueError:
                    return Response(
                        {'status': 'error', 'message': '日期格式无效，请使用 YYYY-MM-DD 格式'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # 使用 values() 减少序列化开销
            data = queryset.values(
                'date',
                'first_buy_point',
                'second_buy_point',
                'stop_loss_point',
                'take_profit_point',
                'strategy_type',
                'signal_strength',
                'current_status',
                'first_buy_time',
                'second_buy_time',
                'take_profit_time',
                'stop_loss_time',
                'stock__ts_code',
                'stock__name'
            )
            
            # 格式化日期字段
            formatted_data = []
            for item in data:
                formatted_item = {
                    'date': item['date'].strftime('%Y-%m-%d'),
                    'first_buy_point': item['first_buy_point'],
                    'second_buy_point': item['second_buy_point'],
                    'stop_loss_point': item['stop_loss_point'],
                    'take_profit_point': item['take_profit_point'],
                    'strategy_type': item['strategy_type'],
                    'signal_strength': item['signal_strength'],
                    'current_status': item['current_status'],
                    'stock__ts_code': item['stock__ts_code'],
                    'stock__name': item['stock__name'],
                    'first_buy_time': item['first_buy_time'].strftime('%Y-%m-%d') if item['first_buy_time'] else None,
                    'second_buy_time': item['second_buy_time'].strftime('%Y-%m-%d') if item['second_buy_time'] else None,
                    'take_profit_time': item['take_profit_time'].strftime('%Y-%m-%d') if item['take_profit_time'] else None,
                    'stop_loss_time': item['stop_loss_time'].strftime('%Y-%m-%d') if item['stop_loss_time'] else None
                }
                formatted_data.append(formatted_item)
            
            return Response({
                'status': 'success',
                'message': f'找到 {len(formatted_data)} 条策略记录',
                'data': formatted_data
            })
            
        except Exception as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request):
        try:
            # 获取参数
            trade_date = request.data.get('trade_date')
            start_date = request.data.get('start_date')
            end_date = request.data.get('end_date')
            
            if not (trade_date or start_date):
                return Response(
                    {'status': 'error', 'message': '请提供 trade_date 或 start_date'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            dates_to_analyze = []
            fetcher = StockDataFetcher()
            
            # 处理不同的日期参数组合
            if trade_date:
                try:
                    query_date = datetime.strptime(trade_date, '%Y-%m-%d').date()
                    # 检查数据是否已存在
                    if not PolicyDetails.objects.filter(date=query_date).exists():
                        result = fetcher.analyze_stock_pattern(trade_date)
                        if result['status'] == 'success':
                            return Response(result)
                    else:
                        return Response({
                            'status': 'success',
                            'message': '该日期的数据已存在',
                            'data': []
                        })
                except ValueError:
                    return Response(
                        {'status': 'error', 'message': 'trade_date 格式无效，请使用 YYYY-MM-DD 格式'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            elif start_date:
                try:
                    start = datetime.strptime(start_date, '%Y-%m-%d').date()
                    if end_date:
                        end = datetime.strptime(end_date, '%Y-%m-%d').date()
                    else:
                        end = datetime.now().date()
                        
                    if start > end:
                        return Response(
                            {'status': 'error', 'message': 'start_date 不能晚于 end_date'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    # 获取需要分析的日期列表
                    trading_days = TradingCalendar.objects.filter(
                        date__range=[start, end],
                        is_trading_day=True
                    ).order_by('date')
                    
                    # 过滤掉已有数据的日期
                    existing_dates = set(PolicyDetails.objects.filter(
                        date__range=[start, end]
                    ).values_list('date', flat=True))
                    
                    all_results = []
                    for trading_day in trading_days:
                        if trading_day.date not in existing_dates:
                            result = fetcher.analyze_stock_pattern(
                                trading_day.date.strftime('%Y-%m-%d')
                            )
                            if result['status'] == 'success':
                                all_results.extend(result.get('data', []))
                    
                    return Response({
                        'status': 'success',
                        'message': f'成功分析并保存了 {len(all_results)} 条数据',
                        'data': all_results
                    })
                    
                except ValueError:
                    return Response(
                        {'status': 'error', 'message': '日期格式无效，请使用 YYYY-MM-DD 格式'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
        except Exception as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class StrategyStatsView(generics.ListCreateAPIView):
    """策略统计视图
    
    GET: 获取策略统计列表，支持以下过滤：
    - date: 具体日期
    - start_date & end_date: 日期范围
    - stock: 股票代码
    
    POST: 创建新的策略统计记录
    """
    queryset = StrategyStats.objects.all()
    serializer_class = StrategyStatsSerializer
    filterset_fields = ['date', 'stock']

    def get_queryset(self):
        queryset = super().get_queryset()
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
            
        return queryset

    def create(self, request, *args, **kwargs):
        """创建策略统计记录
        
        自动从analyze_signals的结果中创建统计记录
        """
        try:
            # 获取分析日期范围
            start_date = request.data.get('start_date')
            end_date = request.data.get('end_date')
            stock_code = request.data.get('stock_code')  # 可选参数
            
            print(f"Received request data: {request.data}")  # 添加日志
            print(f"Stock code: {stock_code}")  # 添加日志
            
            # 验证日期格式
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': '日期格式无效，请使用 YYYY-MM-DD 格式'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 获取或创建策略分析视图实例
            analysis_view = ManualStrategyAnalysisView()
            
            # 获取股票对象
            stock = None
            if stock_code:
                try:
                    stock = Code.objects.get(ts_code=stock_code)
                    print(f"Found stock: {stock.name} ({stock.ts_code})")  # 添加日志
                except Code.DoesNotExist:
                    print(f"Stock not found: {stock_code}")  # 添加日志
                    return Response(
                        {'error': f'股票代码 {stock_code} 不存在'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # 执行策略分析
            stats = analysis_view.analyze_signals(start_date, end_date, stock_code)
            
            # 准备统计数据
            stats_data = {
                'date': end_date,
                'stock': stock.pk if stock else None,  # 这里是正确的
                'total_signals': stats['total'],
                'first_buy_success': stats['first_buy_success'],
                'second_buy_success': stats['second_buy_success'],
                'failed_signals': stats['failed'],
                'success_rate': round((stats['first_buy_success'] + stats['second_buy_success']) / stats['total'] * 100, 2) if stats['total'] > 0 else 0.00,
                'avg_hold_days': stats['avg_hold_days'],
                'max_drawdown': stats['max_drawdown'],
                'profit_0_3': stats['profit_distribution']['0-3%'],
                'profit_3_5': stats['profit_distribution']['3-5%'],
                'profit_5_7': stats['profit_distribution']['5-7%'],
                'profit_7_10': stats['profit_distribution']['7-10%'],
                'profit_above_10': stats['profit_distribution']['>10%']
            }
            
            # 创建序列化器和保存数据
            serializer = self.get_serializer(data=stats_data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            
            # 这里的 analyzed_stocks 没有定义，需要从 stats 中获取
            response_data = {
                'status': 'success',
                'message': '策略统计记录创建成功',
                'data': serializer.data,
                'analysis_info': {
                    'date_range': f"{start_date} to {end_date}",
                    'analyzed_stocks': stats['analyzed_stocks'],
                    'total_signals': stats['total'],
                    'data_summary': {
                        'min_records': stats['data_stats']['min_records'],
                        'max_records': stats['data_stats']['max_records'],
                        'avg_records': stats['data_stats']['avg_records'],
                        'total_records': stats['data_stats']['total_records'],
                        'avg_records_per_stock': stats['avg_records_per_stock']
                    }
                }
            }
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


