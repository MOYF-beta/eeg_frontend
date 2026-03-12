from django.urls import path
from .consumers import EegStreamConsumer
from .graph_consumer_v2 import EegGraphConsumerV2
from .graph_sync_consumer import GraphSyncConsumer

websocket_urlpatterns = [
    path('ws/stream/', EegStreamConsumer.as_asgi()),
    path('ws/eeg/', EegGraphConsumerV2.as_asgi()),  # 计算图数据流
    path('ws/graph-sync/', GraphSyncConsumer.as_asgi()),  # 计算图状态同步
]
