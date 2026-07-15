from django.urls import path
from .graph_consumer_v2 import EegGraphConsumerV2
from .graph_sync_consumer import GraphSyncConsumer
from .control_consumer import ControlConsumer

websocket_urlpatterns = [
    path('ws/eeg/', EegGraphConsumerV2.as_asgi()),  # 纯数据流
    path('ws/control/', ControlConsumer.as_asgi()),  # 统一控制通道
    path('ws/graph-sync/', GraphSyncConsumer.as_asgi()),  # 兼容保留：图状态同步
]
