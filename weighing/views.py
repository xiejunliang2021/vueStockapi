from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import WeighingRecord
from .serializers import WeighingRecordSerializer

class WeighingRecordViewSet(viewsets.ModelViewSet):
    queryset = WeighingRecord.objects.all()
    serializer_class = WeighingRecordSerializer
    permission_classes = [IsAuthenticated]

# Create your views here.
