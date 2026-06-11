from django.urls import path
from .views import GeocodeView, PlanTripView

urlpatterns = [
    path('plan-trip/', PlanTripView.as_view(), name='plan-trip'),
    path('geocode/', GeocodeView, name='geocode'),
]