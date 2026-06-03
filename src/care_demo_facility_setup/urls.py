from django.conf import settings
from django.shortcuts import HttpResponse
from django.urls import path
from rest_framework.routers import DefaultRouter, SimpleRouter

from care_demo_facility_setup.api.viewsets import BaseViewSet


def healthy(request):
    return HttpResponse("OK")


router = DefaultRouter() if settings.DEBUG else SimpleRouter()
router.register(r"", BaseViewSet, basename="care_demo_facility_setup-demo")

urlpatterns = [
    path("health", healthy),
] + router.urls
