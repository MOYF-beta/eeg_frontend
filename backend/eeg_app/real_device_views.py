"""真实设备管理API视图

统一响应格式: {ok: bool, data?: any, error?: string}
"""

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .real_device_manager import (
    scan_serial_ports,
    connect_real_device,
    start_device_acquisition,
    stop_device_acquisition,
    disconnect_real_device,
    get_device_status,
    get_all_connected_devices,
    get_debug_output
)
from .serial_simulator import (
    start_wearable_serial_simulator,
    stop_wearable_serial_simulator,
    list_wearable_serial_simulators,
)
from .device_store import get_all_devices, update_device, create_device


@csrf_exempt
def scan_ports(request):
    """扫描可用的串口设备

    GET /api/real-devices/scan-ports/
    """
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        ports = scan_serial_ports()
        return JsonResponse({
            'ok': True,
            'data': {'ports': ports, 'count': len(ports)}
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Failed to scan ports: {str(e)}'}, status=500)


@csrf_exempt
def connect_device(request):
    """连接真实设备

    POST /api/real-devices/connect/
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        port = data.get('port')
        baudrate = data.get('baudrate', 460800)

        if not port:
            return JsonResponse({'ok': False, 'error': 'Port is required'}, status=400)

        result = connect_real_device(port, baudrate)

        if result['success']:
            device_id = data.get('device_id')
            if device_id:
                devices_list = get_all_devices()
                device = next((d for d in devices_list if d['id'] == device_id), None)
                if device and device['type'] == 'wearable_eeg':
                    update_device(device_id, {
                        'config': {**device.get('config', {}), 'port': port, 'baudrate': baudrate, 'connected': True}
                    })
            else:
                devices_list = get_all_devices()
                existing_device = None
                for device in devices_list:
                    if device.get('type') == 'wearable_eeg':
                        if device.get('config', {}).get('port') == port:
                            existing_device = device
                            break
                if existing_device:
                    device_id = existing_device['id']
                    update_device(device_id, {
                        'config': {**existing_device.get('config', {}), 'port': port, 'baudrate': baudrate, 'connected': True}
                    })
                else:
                    import time
                    device_id = f'real-dev-{int(time.time() * 1000)}'
                    create_device({
                        'id': device_id,
                        'name': f'可穿戴EEG设备 ({port})',
                        'type': 'wearable_eeg',
                        'sampling_rate': 1000,
                        'channel_count': 8,
                        'config': {'port': port, 'baudrate': baudrate, 'connected': True}
                    })

            return JsonResponse({'ok': True, 'data': result['device']})
        else:
            error_message = result.get('error', 'Failed to connect device')
            status_code = 403 if ('Permission denied' in error_message or 'Access is denied' in error_message) else 500
            return JsonResponse({'ok': False, 'error': error_message}, status=status_code)

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

        result = start_device_acquisition(port)

        if result['success']:
            devices_list = get_all_devices()
            for device in devices_list:
                if device['type'] == 'wearable_eeg' and device.get('config', {}).get('port') == port:
                    update_device(device['id'], {
                        'config': {**device.get('config', {}), 'acquiring': True}
                    })
                    break
            return JsonResponse({'ok': True, 'data': {'port': port, 'status': 'acquiring'}})
        else:
            return JsonResponse({'ok': False, 'error': result.get('error', 'Failed to start acquisition')}, status=500)

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

        result = stop_device_acquisition(port)

        if result['success']:
            devices_list = get_all_devices()
            for device in devices_list:
                if device['type'] == 'wearable_eeg' and device.get('config', {}).get('port') == port:
                    update_device(device['id'], {
                        'config': {**device.get('config', {}), 'acquiring': False}
                    })
                    break
            return JsonResponse({'ok': True, 'data': {'port': port, 'status': 'connected'}})
        else:
            return JsonResponse({'ok': False, 'error': result.get('error', 'Failed to stop acquisition')}, status=500)

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

        result = disconnect_real_device(port)

        if result['success']:
            devices_list = get_all_devices()
            for device in devices_list:
                if device['type'] == 'wearable_eeg' and device.get('config', {}).get('port') == port:
                    update_device(device['id'], {
                        'config': {**device.get('config', {}), 'connected': False, 'acquiring': False}
                    })
                    break
            return JsonResponse({'ok': True, 'data': {'port': port, 'status': 'disconnected'}})
        else:
            return JsonResponse({'ok': False, 'error': result.get('error', 'Failed to disconnect device')}, status=500)

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
        if port:
            result = get_device_status(port)
            if result['success']:
                return JsonResponse({'ok': True, 'data': result['device']})
            else:
                return JsonResponse({'ok': False, 'error': result.get('error', 'Device not found')}, status=404)
        else:
            result = get_all_connected_devices()
            return JsonResponse({'ok': True, 'data': {'devices': result['devices'], 'count': len(result['devices'])}})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Failed to get device status: {str(e)}'}, status=500)


@csrf_exempt
def real_devices(request):
    """真实设备管理主入口

    GET /api/real-devices/ - 获取所有真实设备信息
    """
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        all_devices = get_all_devices()
        real_devices = []
        for device in all_devices:
            if device['type'] == 'wearable_eeg':
                port = device.get('config', {}).get('port')
                if port:
                    status_result = get_device_status(port)
                    if status_result['success']:
                        device['connection_status'] = status_result['device']
                    else:
                        device['connection_status'] = {'port': port, 'status': 'disconnected', 'last_error': 'Not connected'}
                else:
                    device['connection_status'] = {'status': 'disconnected', 'last_error': 'No port configured'}
                real_devices.append(device)

        return JsonResponse({'ok': True, 'data': {'devices': real_devices, 'count': len(real_devices)}})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Failed to get real devices: {str(e)}'}, status=500)


@csrf_exempt
def debug_output(request):
    """获取串口调试输出（最近数据帧）

    GET /api/real-devices/debug-output/?port=/dev/ttyUSB0&count=200
    """
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        port = request.GET.get('port')
        count = int(request.GET.get('count', '200'))
        count = max(1, min(2000, count))
        result = get_debug_output(port=port, count=count)
        return JsonResponse({'ok': True, 'data': result})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Failed to get debug output: {str(e)}'}, status=500)


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