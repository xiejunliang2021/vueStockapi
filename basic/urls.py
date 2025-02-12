from django.urls import path
from .views import PolicyDetailsListCreateView

urlpatterns = [
    path('policy-details/', PolicyDetailsListCreateView.as_view(), name='policy-details-list-create'),
]

