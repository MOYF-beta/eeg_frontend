from django.urls import path
from .graph_consumer_v2 import EegGraphConsumerV2
from .control_consumer import ControlConsumer

websocket_urlpatterns = [
    path('ws/eeg/', EegGraphConsumerV2.as_asgi()),    # 纯数据流（OUTPUT 节点实时数据）
    path('ws/control/', ControlConsumer.as_asgi()),   # 统一控制通道（图同步 + 运行时控制）
]
