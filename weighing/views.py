from rest_framework import viewsets
from .models import WeighingRecord
from .serializers import WeighingRecordSerializer

class WeighingRecordViewSet(viewsets.ModelViewSet):
    queryset = WeighingRecord.objects.all()
    serializer_class = WeighingRecordSerializer

# Create your views here.
