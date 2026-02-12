from django.urls import path
from .consumers import EegStreamConsumer
from .graph_consumer import EegGraphConsumer

websocket_urlpatterns = [
    path('ws/stream/', EegStreamConsumer.as_asgi()),
    path('ws/eeg/', EegGraphConsumer.as_asgi()),  # 计算图数据流
]
