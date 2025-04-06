from rest_framework import serializers
from .models import WeighingRecord

class WeighingRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeighingRecord
        fields = '__all__'
