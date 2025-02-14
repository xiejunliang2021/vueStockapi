from rest_framework import serializers
from .models import PolicyDetails, Code

class PolicyDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyDetails
        fields = '__all__'


class CodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Code
        fields = '__all__'
