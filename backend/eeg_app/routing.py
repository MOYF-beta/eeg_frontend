from django.urls import path
from .consumers import EegStreamConsumer

websocket_urlpatterns = [
    path('ws/stream/', EegStreamConsumer.as_asgi()),
]
