from django.urls import path
from . import views
from . import real_device_views

urlpatterns = [
    path('health/', views.health),
    path('status/', views.status),
    path('devices/', views.devices),
    path('devices/<str:device_id>/', views.devices),
    path('graph/', views.graph),                              # GET 读图（初始加载）
    path('graph/python/prototype/', views.graph_python_prototype),
    path('graph/python/library/', views.graph_python_library),
    path('graph/debug/', views.graph_debug),
    path('saved-files/', views.saved_files),
    path('replayable-files/', views.replayable_files),
    
    # 统一设备管理API（唯一数据源）
    path('real-devices/', real_device_views.real_devices),
    path('real-devices/drivers/', real_device_views.list_drivers),
    path('real-devices/scan-ports/', real_device_views.scan_ports),
    path('real-devices/connect/', real_device_views.connect_device),
    path('real-devices/status/', real_device_views.device_status),
    path('real-devices/debug-output/', real_device_views.debug_output),
    path('real-devices/simulator/start/', real_device_views.simulator_start),
    path('real-devices/simulator/stop/', real_device_views.simulator_stop),
    path('real-devices/simulator/status/', real_device_views.simulator_status),
    path('real-devices/simulator/<path:port>/stop/', real_device_views.simulator_stop),
    path('real-devices/test-hook/faulty-driver/', real_device_views.test_hook_faulty_driver),
    path('real-devices/<path:port>/status/', real_device_views.device_status),
    path('real-devices/<path:port>/start-acquisition/', real_device_views.start_acquisition),
    path('real-devices/<path:port>/stop-acquisition/', real_device_views.stop_acquisition),
    path('real-devices/<path:port>/disconnect/', real_device_views.disconnect_device),
    path('real-devices/<str:device_id>/', real_device_views.real_devices),
    path('graph/record/', views.graph_record),
]
