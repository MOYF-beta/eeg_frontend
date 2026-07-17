"""统一设备管理API视图

统一响应格式: {ok: bool, data?: any, error?: string}

所有设备操作通过 DeviceDriverManager 统一路由。
URL 中的 <port> 参数兼容旧格式（如 /dev/ttyUSB0），但内部已改用 device_id 路由。
GET /api/real-devices/ 是唯一的设备列表数据源（直接调 manager.discover_all()）。
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


def _extract_device_id(store_id: str) -> str:
    """从复合 ID 中提取 driver 层面的 device_id。

    兼容 'driver_type:device_id' 格式和纯 device_id。
    """
    if ':' in store_id:
        parts = store_id.split(':', 1)
        # 如果冒号后是路径（如 /dev/ttyUSB0），则取冒号后的部分
        return parts[1] if parts[1] else store_id
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

        device_id = _extract_device_id(port)
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

        device_id = _extract_device_id(port)
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

        device_id = _extract_device_id(port)
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
            device_id = _extract_device_id(port)
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
def real_devices(request, device_id=None):
    """统一设备管理主入口

    GET   /api/real-devices/                   - 获取所有设备（唯一数据源）
    GET   /api/real-devices/{device_id}/       - 获取单个设备
    POST  /api/real-devices/                   - 创建设备（注册到 manager）
    PATCH /api/real-devices/{device_id}/       - 更新设备别名/配置
    DELETE /api/real-devices/{device_id}/      - 删除/断开设备
    """
    if request.method == 'GET':
        return _get_devices(request, device_id)
    elif request.method == 'POST':
        return _create_device(request)
    elif request.method == 'PATCH':
        return _update_device(request, device_id)
    elif request.method == 'DELETE':
        return _delete_device(request, device_id)
    return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)


def _get_devices(request, device_id=None):
    """获取设备列表或单个设备 — 直接从 manager.discover_all() 获取实时数据。"""
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
                'status': 'online' if status != DeviceStatus.DISCONNECTED else 'offline',
                'connection_status': {
                    'port': meta.device_id,
                    'status': status.value,
                    'pending_count': manager.pending_count(meta.device_id),
                },
                'config': {
                    'device_id': meta.device_id,
                    'address': meta.address,
                    'connected': status in (DeviceStatus.CONNECTED, DeviceStatus.ACQUIRING),
                    'acquiring': status == DeviceStatus.ACQUIRING,
                    **meta.extra,
                },
            })

        if device_id:
            # 单个设备查询
            raw_id = _extract_device_id(device_id)
            device = next((d for d in device_list if d['device_id'] == raw_id or d['id'] == device_id), None)
            if not device:
                return JsonResponse({'ok': False, 'error': f'Device {device_id} not found'}, status=404)
            return JsonResponse({'ok': True, 'data': device})

        return JsonResponse({'ok': True, 'data': {'devices': device_list, 'count': len(device_list)}})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Failed to get devices: {str(e)}'}, status=500)


def _create_device(request):
    """创建/注册设备。

    对于虚拟设备和真实设备，设备发现由各自驱动自动完成。
    此端点主要用于记录用户自定义设备配置（如别名）。
    """
    try:
        data = json.loads(request.body)
        name = data.get('name', f'设备 {int(time.time() * 1000) % 10000}')
        device_type = data.get('type', 'simulated')
        sampling_rate = int(data.get('sampling_rate', 250))
        channel_count = int(data.get('channel_count', 8))
        address = data.get('address', '')

        # 构造设备信息返回（实际设备由驱动发现，这里仅返回确认）
        device_info = {
            'id': f'{device_type}:{address or name}',
            'name': name,
            'type': device_type,
            'sampling_rate': sampling_rate,
            'channel_count': channel_count,
            'status': 'ready',
            'config': {'address': address},
        }
        return JsonResponse({'ok': True, 'data': device_info}, status=201)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Failed to create device: {str(e)}'}, status=500)


def _update_device(request, device_id):
    """更新设备配置（别名等）。"""
    if not device_id:
        return JsonResponse({'ok': False, 'error': 'Device ID is required'}, status=400)
    try:
        data = json.loads(request.body)
        manager = get_device_manager()
        raw_id = _extract_device_id(device_id)
        meta = manager.get_device_meta(raw_id)
        if not meta:
            return JsonResponse({'ok': False, 'error': f'Device {device_id} not found'}, status=404)

        updated = {
            'id': f'{meta.driver_type}:{meta.device_id}',
            'name': data.get('name', meta.name),
            'type': meta.driver_type,
            'sampling_rate': int(data.get('sampling_rate', meta.sample_rate)),
            'channel_count': meta.channel_count,
        }
        return JsonResponse({'ok': True, 'data': updated})
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Failed to update device: {str(e)}'}, status=500)


def _delete_device(request, device_id):
    """删除/断开设备连接。"""
    if not device_id:
        return JsonResponse({'ok': False, 'error': 'Device ID is required'}, status=400)
    try:
        manager = get_device_manager()
        raw_id = _extract_device_id(device_id)
        meta = manager.get_device_meta(raw_id)
        if not meta:
            return JsonResponse({'ok': False, 'error': f'Device {device_id} not found'}, status=404)

        # 断开连接
        manager.disconnect(raw_id)
        return JsonResponse({'ok': True, 'data': {'id': device_id, 'disconnected': True}})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Failed to delete device: {str(e)}'}, status=500)


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
            device_id = _extract_device_id(port)
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