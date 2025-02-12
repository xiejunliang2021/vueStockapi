from rest_framework import serializers
from .models import PolicyDetails2

class PolicyDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyDetails2
        fields = '__all__'

