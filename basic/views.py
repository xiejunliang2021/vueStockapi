from rest_framework import generics
from .models import PolicyDetails, Code
from .serializers import PolicyDetailsSerializer, CodeSerializer
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .analysis import ContinuousLimitStrategy
from datetime import datetime

class PolicyDetailsListCreateView(generics.ListCreateAPIView):
    queryset = PolicyDetails.objects.all()
    serializer_class = PolicyDetailsSerializer


class CodeListCreateView(generics.ListCreateAPIView):
    queryset = Code.objects.all()
    serializer_class = CodeSerializer

class CodeRetrieveUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
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


