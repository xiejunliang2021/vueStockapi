from rest_framework import generics
from .models import PolicyDetails2
from .serializers import PolicyDetailsSerializer
from django.shortcuts import render
class PolicyDetailsListCreateView(generics.ListCreateAPIView):
    queryset = PolicyDetails2.objects.all()
    serializer_class = PolicyDetailsSerializer
