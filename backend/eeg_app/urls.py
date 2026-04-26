from django.urls import path
from . import views
from . import real_device_views

urlpatterns = [
    path('health/', views.health),
    path('devices/', views.devices),
    path('devices/<str:device_id>/', views.devices),
    path('graph/', views.graph),
    path('graph/sync/', views.graph_sync),
    path('graph/save/', views.graph_save),
    path('graph/python/prototype/', views.graph_python_prototype),
    path('graph/python/library/', views.graph_python_library),
    path('graph/freeze/', views.graph_freeze),
    path('graph/run/', views.graph_run),
    path('graph/debug/', views.graph_debug),
    path('saved-files/', views.saved_files),
    path('replayable-files/', views.replayable_files),
    
    # 真实设备管理API
    path('real-devices/', real_device_views.real_devices),
    path('real-devices/scan-ports/', real_device_views.scan_ports),
    path('real-devices/connect/', real_device_views.connect_device),
    path('real-devices/status/', real_device_views.device_status),
    path('real-devices/debug-output/', real_device_views.debug_output),
    path('real-devices/simulator/start/', real_device_views.simulator_start),
    path('real-devices/simulator/stop/', real_device_views.simulator_stop),
    path('real-devices/simulator/status/', real_device_views.simulator_status),
    path('real-devices/simulator/<path:port>/stop/', real_device_views.simulator_stop),
    path('real-devices/<path:port>/status/', real_device_views.device_status),
    path('real-devices/<path:port>/start-acquisition/', real_device_views.start_acquisition),
    path('real-devices/<path:port>/stop-acquisition/', real_device_views.stop_acquisition),
    path('real-devices/<path:port>/disconnect/', real_device_views.disconnect_device),
]
