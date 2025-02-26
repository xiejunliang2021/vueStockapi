from rest_framework import generics
from .models import PolicyDetails, Code, TradingCalendar, StockDailyData
from .serializers import PolicyDetailsSerializer, CodeSerializer, TradingCalendarSerializer, StockPatternAnalysisSerializer, StockPatternResultSerializer
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .analysis import ContinuousLimitStrategy
from datetime import datetime
from .utils import StockDataFetcher

class PolicyDetailsListCreateView(generics.ListCreateAPIView):
    """策略详情列表和创建视图"""
    queryset = PolicyDetails.objects.all()
    serializer_class = PolicyDetailsSerializer


class CodeListCreateView(generics.ListCreateAPIView):
    """股票代码列表和创建视图"""
    queryset = Code.objects.all()
    serializer_class = CodeSerializer

class CodeRetrieveUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    """股票代码详情、更新和删除视图"""
    queryset = Code.objects.all()
    serializer_class = CodeSerializer
    lookup_field = 'ts_code'

class ManualStrategyAnalysisView(APIView):
    """手动策略分析视图"""
    
    def analyze_signals(self, start_date, end_date, stock_code=None):
        """分析策略信号"""
        try:
            # 初始化计数器
            stats = {
                'first_buy_success': 0,  # 第一买点成功次数
                'second_buy_success': 0,  # 第二买点成功次数
                'failed': 0,             # 失败次数
                'total': 0               # 总信号数
            }
            
            # 获取策略数据
            signals_query = PolicyDetails.objects.filter(
                date__range=[start_date, end_date],
                current_status='L'  # 只分析进行中的信号
            ).select_related('stock')
            
            if stock_code:
                signals_query = signals_query.filter(stock__ts_code=stock_code)
            
            # 遍历每个信号
            for signal in signals_query:
                stats['total'] += 1
                
                # 获取信号日期之后的日线数据
                daily_data = StockDailyData.objects.filter(
                    stock=signal.stock,
                    trade_date__gt=signal.date
                ).order_by('trade_date')
                
                first_buy_point = float(signal.first_buy_point)
                first_stop_loss = first_buy_point * 0.9  # 第一买点止损价
                second_stop_loss = first_buy_point * 0.8  # 第二买点止损价
                
                for day_data in daily_data:
                    low_price = float(day_data.low)
                    high_price = float(day_data.high)
                    
                    # 第一种情况：第一买点成功
                    if low_price <= first_buy_point:
                        holding_price = first_buy_point
                        # 检查后续数据
                        success = False
                        for next_day in daily_data.filter(trade_date__gt=day_data.trade_date):
                            next_low = float(next_day.low)
                            next_high = float(next_day.high)
                            if next_low > first_stop_loss and next_high > holding_price * 1.075:
                                success = True
                                break
                            elif next_low <= second_stop_loss:
                                success = False
                                break
                        
                        if success:
                            signal.current_status = 'S'
                            signal.holding_price = holding_price
                            signal.save()
                            stats['first_buy_success'] += 1
                        else:
                            signal.current_status = 'F'
                            signal.holding_price = holding_price
                            signal.save()
                            stats['failed'] += 1
                        break
                    
                    # 第二种情况：第二买点成功
                    elif low_price <= first_stop_loss and low_price > second_stop_loss:
                        holding_price = (first_buy_point + first_stop_loss) / 2
                        # 检查后续数据
                        success = False
                        for next_day in daily_data.filter(trade_date__gt=day_data.trade_date):
                            if float(next_day.high) >= holding_price * 1.075:
                                success = True
                                break
                            elif float(next_day.low) <= second_stop_loss:
                                success = False
                                break
                        
                        if success:
                            signal.current_status = 'S'
                            signal.holding_price = holding_price
                            signal.save()
                            stats['second_buy_success'] += 1
                        else:
                            signal.current_status = 'F'
                            signal.holding_price = holding_price
                            signal.save()
                            stats['failed'] += 1
                        break
                    
                    # 第三种情况：失败
                    elif low_price <= second_stop_loss:
                        signal.current_status = 'F'
                        signal.holding_price = second_stop_loss
                        signal.save()
                        stats['failed'] += 1
                        break
            
            return stats
            
        except Exception as e:
            raise Exception(f"策略分析失败: {str(e)}")

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
            
            # 计算成功率
            total_signals = stats['total']
            total_success = stats['first_buy_success'] + stats['second_buy_success']
            success_rate = (total_success / total_signals * 100) if total_signals > 0 else 0
            
            return Response({
                'status': 'success',
                'message': '策略分析完成',
                'data': {
                    'total_signals': total_signals,
                    'first_buy_success': stats['first_buy_success'],
                    'second_buy_success': stats['second_buy_success'],
                    'failed': stats['failed'],
                    'success_rate': f"{success_rate:.2f}%"
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
                      'strategy_type', 'signal_strength', 'current_status')
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
                'stock__ts_code',
                'stock__name'
            )
            
            return Response({
                'status': 'success',
                'message': f'找到 {len(data)} 条策略记录',
                'data': list(data)
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


