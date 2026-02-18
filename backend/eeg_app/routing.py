from django.urls import path
from .consumers import EegStreamConsumer
from .graph_consumer_v2 import EegGraphConsumerV2

websocket_urlpatterns = [
    path('ws/stream/', EegStreamConsumer.as_asgi()),
    path('ws/eeg/', EegGraphConsumerV2.as_asgi()),  # 计算图数据流
]
