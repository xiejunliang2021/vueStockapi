from rest_framework import generics
from .models import PolicyDetails, Code
from .serializers import PolicyDetailsSerializer, CodeSerializer
from django.shortcuts import render
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


