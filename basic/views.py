from rest_framework import generics
from .models import PolicyDetails, Code, TradingCalendar
from .serializers import PolicyDetailsSerializer, CodeSerializer, TradingCalendarSerializer, StockPatternAnalysisSerializer, StockPatternResultSerializer
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .analysis import ContinuousLimitStrategy
from datetime import datetime
from .utils import StockDataFetcher
from django.core.cache import cache

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
    """手动策略分析视图
    
    提供手动触发策略分析的API接口
    
    接口说明：
    POST /api/manual-analysis/
    
    请求参数：
    - start_date: 开始日期（YYYY-MM-DD）
    - end_date: 结束日期（YYYY-MM-DD）
    - stock_code: 股票代码
    
    返回数据：
    - message: 处理结果说明
    - signals_count: 生成的信号数量
    
    错误处理：
    - 400: 日期格式无效
    - 500: 服务器处理错误
    """
    def post(self, request):
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        stock_code = request.data.get('stock_code')

        try:
            # 验证日期格式
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

            # 检查是否已有数据
            existing_signals = PolicyDetails.objects.filter(
                stock__ts_code=stock_code,
                date__range=[start_date, end_date]
            ).exists()

            if not existing_signals:
                strategy = ContinuousLimitStrategy()
                signals = strategy.analyze_stock(
                    stock_code,
                    start_date.strftime('%Y%m%d'),
                    end_date.strftime('%Y%m%d')
                )
                strategy.save_signals(signals)
                return Response({'message': '策略分析完成', 'signals_count': len(signals)})
            else:
                return Response({'message': '该时间段的数据已存在'})

        except ValueError:
            return Response({'error': '日期格式无效'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
    """更新股票日线数据视图
    
    功能说明：
    1. 支持单日数据更新和日期范围更新
    2. 自动验证交易日
    3. 自动过滤无效股票代码
    4. 批量保存数据
    5. 自动清理旧数据
    
    请求参数：
    - trade_date: 单个交易日期（YYYY-MM-DD格式）
    - start_date: 开始日期（YYYY-MM-DD格式）
    - end_date: 结束日期（YYYY-MM-DD格式）
    """
    
    def post(self, request):
        trade_date = request.data.get('trade_date')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        
        try:
            # 参数验证
            if not (trade_date or (start_date and end_date)):
                return Response(
                    {'error': '请提供 trade_date 或 start_date 和 end_date'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 日期格式验证
            if trade_date:
                try:
                    datetime.strptime(trade_date, '%Y-%m-%d')
                except ValueError:
                    return Response(
                        {'error': 'trade_date 格式无效，请使用 YYYY-MM-DD 格式'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                try:
                    start = datetime.strptime(start_date, '%Y-%m-%d')
                    end = datetime.strptime(end_date, '%Y-%m-%d')
                    if start > end:
                        return Response(
                            {'error': 'start_date 不能晚于 end_date'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                except ValueError:
                    return Response(
                        {'error': '日期格式无效，请使用 YYYY-MM-DD 格式'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # 获取数据
            fetcher = StockDataFetcher()
            
            if trade_date:
                result = fetcher.update_all_stocks_daily_data(trade_date=trade_date)
            else:
                result = fetcher.update_all_stocks_daily_data(
                    start_date=start_date,
                    end_date=end_date
                )
            
            # 根据结果状态返回不同的响应
            if result['status'] == 'success':
                return Response({
                    'status': 'success',
                    'message': result['message']
                })
            elif result['status'] == 'skipped':
                return Response({
                    'status': 'skipped',
                    'message': result['message']
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'status': 'failed',
                    'message': result['message']
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            # 记录详细错误信息
            print(f"更新数据时发生错误：{str(e)}")
            return Response(
                {
                    'status': 'error',
                    'message': '更新数据失败',
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class StockPatternAnalysisView(APIView):
    """股票模式分析视图"""
    
    def post(self, request):
        serializer = StockPatternAnalysisSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'status': 'error', 'message': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        trade_date = serializer.validated_data['trade_date'].strftime('%Y-%m-%d')
        
        # 使用缓存检查是否已有分析结果
        cache_key = f'stock_pattern_{trade_date}'
        result = cache.get(cache_key)
        
        if not result:
            fetcher = StockDataFetcher()
            result = fetcher.analyze_stock_pattern(trade_date)
            if result['status'] == 'success':
                cache.set(cache_key, result, 3600)  # 缓存1小时
        
        if result['status'] == 'success':
            # 序列化结果数据
            result_serializer = StockPatternResultSerializer(
                data=result['data'], 
                many=True
            )
            if result_serializer.is_valid():
                result['data'] = result_serializer.data
            
            return Response(result)
        else:
            return Response(
                result,
                status=status.HTTP_400_BAD_REQUEST
            )

class PolicyDetailsByDateView(APIView):
    """获取特定日期的策略详情视图"""
    
    def get(self, request, date):
        try:
            # 转换日期格式
            query_date = datetime.strptime(date, '%Y-%m-%d').date()
            
            # 获取指定日期的策略详情
            policies = PolicyDetails.objects.filter(
                date=query_date
            ).select_related('stock')
            
            # 序列化数据
            serializer = PolicyDetailsSerializer(policies, many=True)
            
            return Response({
                'status': 'success',
                'message': f'找到 {len(policies)} 条策略记录',
                'data': serializer.data
            })
            
        except ValueError:
            return Response(
                {'status': 'error', 'message': '日期格式无效'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


