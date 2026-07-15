"""真实设备管理API视图

统一响应格式: {ok: bool, data?: any, error?: string}

所有设备操作通过 DeviceDriverManager 统一路由。
URL 中的 <port> 参数兼容旧格式（如 /dev/ttyUSB0），但内部已改用 device_id 路由。
模拟器端点保留向后兼容，同时 simulator 驱动设备通过标准设备 API 可用。
"""

import json
import time
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .drivers.manager import get_device_manager
from .drivers.base import DeviceStatus
from .serial_simulator import (
    start_wearable_serial_simulator,
    stop_wearable_serial_simulator,
    list_wearable_serial_simulators,
)
from .device_store import get_all_devices, update_device, create_device


def _resolve_device_id(raw: str) -> str:
    """将 URL 中的原始标识解析为 manager 可识别的 device_id。

    支持两种格式：
    - 完整格式 'driver_type:device_id'（如 'wearable_eeg:/dev/ttyUSB0'）
    - 纯 device_id（如 '/dev/ttyUSB0'、'sim_alpha'）
    """
    if not raw:
        return ''
    if ':' in raw:
        return raw
    # 尝试匹配 device_store 中的设备
    for dev in get_all_devices():
        if dev.get('config', {}).get('device_id') == raw:
            return dev['id']
        if dev['id'].endswith(':' + raw):
            return dev['id']
    return raw


def _extract_device_id(store_id: str) -> str:
    """从 device_store ID 中提取 driver 层面的 device_id。"""
    if ':' in store_id:
        return store_id.split(':', 1)[1]
    return store_id


@csrf_exempt
def scan_ports(request):
    """扫描可用的设备

    GET /api/real-devices/scan-ports/
    """
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        manager = get_device_manager()
        devices = manager.discover_all()
        ports = []
        for meta in devices:
            ports.append({
                'port': meta.device_id,
                'description': meta.extra.get('description', ''),
                'manufacturer': meta.extra.get('manufacturer', ''),
                'product': meta.extra.get('product', ''),
                'hwid': meta.extra.get('hwid', ''),
                'is_ch340': meta.extra.get('is_ch340', False),
                'is_available': meta.is_available,
                'vid': meta.extra.get('vid', 'N/A'),
                'pid': meta.extra.get('pid', 'N/A'),
                'driver_type': meta.driver_type,
                'channel_count': meta.channel_count,
                'sample_rate': meta.sample_rate,
            })
        return JsonResponse({
            'ok': True,
            'data': {'ports': ports, 'count': len(ports)}
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Failed to scan ports: {str(e)}'}, status=500)


@csrf_exempt
def connect_device(request):
    """连接设备

    POST /api/real-devices/connect/
    body: {"port": "/dev/ttyUSB0", "baudrate": 460800, "device_id": "..."}
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        port = data.get('port') or data.get('device_id')
        baudrate = data.get('baudrate', 460800)

        if not port:
            return JsonResponse({'ok': False, 'error': 'Port or device_id is required'}, status=400)

        manager = get_device_manager()
        raw_device_id = port
        if ':' in port:
            raw_device_id = _extract_device_id(port)

        ok = manager.connect(raw_device_id, {'baudrate': baudrate})
        status = manager.get_status(raw_device_id)
        meta = manager.get_device_meta(raw_device_id)

        if ok:
            return JsonResponse({
                'ok': True,
                'data': {
                    'device_id': raw_device_id,
                    'port': raw_device_id,
                    'status': status.value,
                    'driver_type': meta.driver_type if meta else '',
                }
            })
        else:
            return JsonResponse({'ok': False, 'error': 'Failed to connect device'}, status=500)

    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Failed to connect device: {str(e)}'}, status=500)


@csrf_exempt
def start_acquisition(request, port=None):
    """开始设备数据采集

    POST /api/real-devices/{port}/start-acquisition/
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        if not port:
            return JsonResponse({'ok': False, 'error': 'Port is required in URL path'}, status=400)

        device_id = _extract_device_id(_resolve_device_id(port))
        manager = get_device_manager()
        ok = manager.start_streaming(device_id)

        if ok:
            return JsonResponse({'ok': True, 'data': {'port': device_id, 'status': 'acquiring'}})
        else:
            return JsonResponse({'ok': False, 'error': f'Failed to start acquisition on {device_id}'}, status=500)

    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Failed to start acquisition: {str(e)}'}, status=500)


@csrf_exempt
def stop_acquisition(request, port=None):
    """停止设备数据采集

    POST /api/real-devices/{port}/stop-acquisition/
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        if not port:
            return JsonResponse({'ok': False, 'error': 'Port is required in URL path'}, status=400)

        device_id = _extract_device_id(_resolve_device_id(port))
        manager = get_device_manager()
        ok = manager.stop_streaming(device_id)

        if ok:
            return JsonResponse({'ok': True, 'data': {'port': device_id, 'status': 'connected'}})
        else:
            return JsonResponse({'ok': False, 'error': f'Failed to stop acquisition on {device_id}'}, status=500)

    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Failed to stop acquisition: {str(e)}'}, status=500)


@csrf_exempt
def disconnect_device(request, port=None):
    """断开设备连接

    POST /api/real-devices/{port}/disconnect/
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        if not port:
            return JsonResponse({'ok': False, 'error': 'Port is required in URL path'}, status=400)

        device_id = _extract_device_id(_resolve_device_id(port))
        manager = get_device_manager()
        ok = manager.disconnect(device_id)

        if ok:
            return JsonResponse({'ok': True, 'data': {'port': device_id, 'status': 'disconnected'}})
        else:
            return JsonResponse({'ok': False, 'error': f'Failed to disconnect device {device_id}'}, status=500)

    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Failed to disconnect device: {str(e)}'}, status=500)


@csrf_exempt
def device_status(request, port=None):
    """获取设备状态

    GET /api/real-devices/status/ - 获取所有设备状态
    GET /api/real-devices/{port}/status/ - 获取单个设备状态
    """
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        manager = get_device_manager()
        if port:
            device_id = _extract_device_id(_resolve_device_id(port))
            status = manager.get_status(device_id)
            meta = manager.get_device_meta(device_id)
            return JsonResponse({
                'ok': True,
                'data': {
                    'port': device_id,
                    'device_id': device_id,
                    'status': status.value,
                    'driver_type': meta.driver_type if meta else '',
                    'pending_count': manager.pending_count(device_id),
                }
            })
        else:
            devices = manager.discover_all()
            device_list = []
            for meta in devices:
                status = manager.get_status(meta.device_id)
                device_list.append({
                    'port': meta.device_id,
                    'device_id': meta.device_id,
                    'status': status.value,
                    'driver_type': meta.driver_type,
                    'pending_count': manager.pending_count(meta.device_id),
                })
            return JsonResponse({'ok': True, 'data': {'devices': device_list, 'count': len(device_list)}})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Failed to get device status: {str(e)}'}, status=500)


@csrf_exempt
def real_devices(request):
    """真实设备管理主入口

    GET /api/real-devices/ - 获取所有设备信息
    """
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        manager = get_device_manager()
        devices = manager.discover_all()
        device_list = []
        for meta in devices:
            status = manager.get_status(meta.device_id)
            device_list.append({
                'id': f'{meta.driver_type}:{meta.device_id}',
                'name': meta.name,
                'type': meta.driver_type,
                'device_id': meta.device_id,
                'port': meta.device_id,
                'sampling_rate': meta.sample_rate,
                'channel_count': meta.channel_count,
                'connection_status': {
                    'port': meta.device_id,
                    'status': status.value,
                    'pending_count': manager.pending_count(meta.device_id),
                },
            })

        return JsonResponse({'ok': True, 'data': {'devices': device_list, 'count': len(device_list)}})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Failed to get real devices: {str(e)}'}, status=500)


@csrf_exempt
def debug_output(request):
    """获取设备调试输出（最近数据帧）

    GET /api/real-devices/debug-output/?port=/dev/ttyUSB0&count=200
    """
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        manager = get_device_manager()
        port = request.GET.get('port')
        count = int(request.GET.get('count', '200'))
        count = max(1, min(2000, count))

        if port:
            device_id = _extract_device_id(_resolve_device_id(port))
            frames = manager.read_data(device_id, count=count)
            samples = [
                {'seq': f.seq, 'timestamp': f.timestamp, 'channels': f.channels, 'port': device_id}
                for f in frames
            ]
            return JsonResponse({
                'ok': True,
                'data': {
                    'ports': [{
                        'port': device_id,
                        'samples': samples,
                        'count': len(samples),
                        'raw_inputs': [],
                        'raw_input_count': 0,
                    }],
                    'total_samples': len(samples),
                }
            })
        else:
            devices = manager.discover_all()
            result_ports = []
            total = 0
            for meta in devices:
                frames = manager.read_data(meta.device_id, count=count)
                samples = [
                    {'seq': f.seq, 'timestamp': f.timestamp, 'channels': f.channels, 'port': meta.device_id}
                    for f in frames
                ]
                total += len(samples)
                result_ports.append({
                    'port': meta.device_id,
                    'samples': samples,
                    'count': len(samples),
                    'raw_inputs': [],
                    'raw_input_count': 0,
                })
            return JsonResponse({
                'ok': True,
                'data': {'ports': result_ports, 'total_samples': total}
            })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Failed to get debug output: {str(e)}'}, status=500)


# ====================================================================== #
#  串口模拟器端点（保留向后兼容，基于 serial_simulator.py 的 pty 模拟器）
# ====================================================================== #

@csrf_exempt
def simulator_start(request):
    """启动可穿戴串口模拟器。

    POST /api/real-devices/simulator/start/
    body: {"sample_rate": 1000, "channels": 8}
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        payload = json.loads(request.body or '{}')
        sample_rate = int(payload.get('sample_rate', 1000))
        channels = int(payload.get('channels', 8))
        status = start_wearable_serial_simulator(sample_rate=sample_rate, channels=channels)
        return JsonResponse({
            'ok': True,
            'data': {
                'port': status.port,
                'sample_rate': status.sample_rate,
                'channels': status.channels,
                'running': status.running,
                'streaming': status.streaming,
                'frames_sent': status.frames_sent,
            }
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Failed to start simulator: {str(e)}'}, status=500)


@csrf_exempt
def simulator_stop(request, port=None):
    """停止指定串口模拟器。

    POST /api/real-devices/simulator/stop/
    POST /api/real-devices/simulator/<path:port>/stop/
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        if not port:
            payload = json.loads(request.body or '{}')
            port = payload.get('port')
        if not port:
            return JsonResponse({'ok': False, 'error': 'port is required'}, status=400)

        ok = stop_wearable_serial_simulator(str(port))
        if not ok:
            return JsonResponse({'ok': False, 'error': f'simulator not found: {port}'}, status=404)
        return JsonResponse({'ok': True, 'data': {'port': str(port), 'stopped': True}})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Failed to stop simulator: {str(e)}'}, status=500)


@csrf_exempt
def simulator_status(request):
    """获取所有串口模拟器状态。

    GET /api/real-devices/simulator/status/
    """
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        simulators = list_wearable_serial_simulators()
        data = []
        for _, status in simulators.items():
            data.append({
                'port': status.port,
                'sample_rate': status.sample_rate,
                'channels': status.channels,
                'running': status.running,
                'streaming': status.streaming,
                'frames_sent': status.frames_sent,
            })
        return JsonResponse({'ok': True, 'data': {'simulators': data, 'count': len(data)}})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Failed to get simulator status: {str(e)}'}, status=500)