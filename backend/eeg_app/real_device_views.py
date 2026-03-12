"""真实设备管理API视图"""

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
from .device_store import get_all_devices, update_device, create_device


@csrf_exempt
def scan_ports(request):
    """扫描可用的串口设备
    
    GET /api/real-devices/scan-ports/
    """
    if request.method != 'GET':
        return JsonResponse({
            'code': 405,
            'message': 'Method not allowed'
        }, status=405)
    
    try:
        ports = scan_serial_ports()
        print(f"[real_device_views] scan_ports api result count={len(ports)}")
        if ports:
            print(f"[real_device_views] scan_ports api ports={[p.get('port') for p in ports]}")
        else:
            print("[real_device_views] scan_ports api returned empty list")
        
        return JsonResponse({
            'code': 0,
            'message': 'success',
            'data': {
                'ports': ports,
                'count': len(ports)
            }
        })
        
    except Exception as e:
        print(f"[real_device_views] scan_ports api error: {e}")
        return JsonResponse({
            'code': 500,
            'message': f'Failed to scan ports: {str(e)}'
        }, status=500)


@csrf_exempt
def connect_device(request):
    """连接真实设备
    
    POST /api/real-devices/connect/
    
    请求体:
    {
        "port": "COM3",
        "baudrate": 460800,
        "device_id": "dev-123"  # 可选，关联的设备ID
    }
    """
    if request.method != 'POST':
        return JsonResponse({
            'code': 405,
            'message': 'Method not allowed'
        }, status=405)
    
    try:
        data = json.loads(request.body)
        
        port = data.get('port')
        baudrate = data.get('baudrate', 460800)
        
        if not port:
            return JsonResponse({
                'code': 400,
                'message': 'Port is required'
            }, status=400)
        
        # 连接设备
        result = connect_real_device(port, baudrate)
        
        if result['success']:
            # 如果提供了device_id，更新设备状态
            device_id = data.get('device_id')
            if device_id:
                # 查找设备
                devices_list = get_all_devices()
                device = next((d for d in devices_list if d['id'] == device_id), None)
                
                if device and device['type'] == 'wearable_eeg':
                    # 更新设备配置
                    update_device(device_id, {
                        'config': {
                            **device.get('config', {}),
                            'port': port,
                            'baudrate': baudrate,
                            'connected': True
                        }
                    })
            else:
                # 如果没有提供device_id，检查是否已存在相同端口的设备
                devices_list = get_all_devices()
                existing_device = None
                
                for device in devices_list:
                    if device.get('type') == 'wearable_eeg':
                        device_port = device.get('config', {}).get('port')
                        if device_port == port:
                            existing_device = device
                            break
                
                if existing_device:
                    # 使用已存在的设备
                    device_id = existing_device['id']
                    # 更新设备连接状态
                    update_device(device_id, {
                        'config': {
                            **existing_device.get('config', {}),
                            'port': port,
                            'baudrate': baudrate,
                            'connected': True
                        }
                    })
                else:
                    # 创建设备记录
                    import time
                    device_id = f'real-dev-{int(time.time() * 1000)}'
                    device_name = f'可穿戴EEG设备 ({port})'
                    
                    # 创建设备
                    create_device({
                        'id': device_id,
                        'name': device_name,
                        'type': 'wearable_eeg',
                        'sampling_rate': 1000,
                        'channel_count': 8,
                        'config': {
                            'port': port,
                            'baudrate': baudrate,
                            'connected': True
                        }
                    })
            
            return JsonResponse({
                'code': 0,
                'message': 'Device connected successfully',
                'data': result['device']
            })
        else:
            error_message = result.get('error', 'Failed to connect device')
            status_code = 403 if ('Permission denied' in error_message or 'Access is denied' in error_message) else 500
            return JsonResponse({
                'code': 500,
                'message': error_message
            }, status=status_code)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'code': 400,
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'code': 500,
            'message': f'Failed to connect device: {str(e)}'
        }, status=500)


@csrf_exempt
def start_acquisition(request, port=None):
    """开始设备数据采集
    
    POST /api/real-devices/{port}/start-acquisition/
    """
    if request.method != 'POST':
        return JsonResponse({
            'code': 405,
            'message': 'Method not allowed'
        }, status=405)
    
    try:
        if not port:
            return JsonResponse({
                'code': 400,
                'message': 'Port is required in URL path'
            }, status=400)
        
        # 开始采集
        result = start_device_acquisition(port)
        
        if result['success']:
            # 更新设备状态
            devices_list = get_all_devices()
            for device in devices_list:
                if device['type'] == 'wearable_eeg' and device.get('config', {}).get('port') == port:
                    update_device(device['id'], {
                        'config': {
                            **device.get('config', {}),
                            'acquiring': True
                        }
                    })
                    break
            
            return JsonResponse({
                'code': 0,
                'message': result['message'],
                'data': {
                    'port': port,
                    'status': 'acquiring'
                }
            })
        else:
            return JsonResponse({
                'code': 500,
                'message': result.get('error', 'Failed to start acquisition')
            }, status=500)
        
    except Exception as e:
        return JsonResponse({
            'code': 500,
            'message': f'Failed to start acquisition: {str(e)}'
        }, status=500)


@csrf_exempt
def stop_acquisition(request, port=None):
    """停止设备数据采集
    
    POST /api/real-devices/{port}/stop-acquisition/
    """
    if request.method != 'POST':
        return JsonResponse({
            'code': 405,
            'message': 'Method not allowed'
        }, status=405)
    
    try:
        if not port:
            return JsonResponse({
                'code': 400,
                'message': 'Port is required in URL path'
            }, status=400)
        
        # 停止采集
        result = stop_device_acquisition(port)
        
        if result['success']:
            # 更新设备状态
            devices_list = get_all_devices()
            for device in devices_list:
                if device['type'] == 'wearable_eeg' and device.get('config', {}).get('port') == port:
                    update_device(device['id'], {
                        'config': {
                            **device.get('config', {}),
                            'acquiring': False
                        }
                    })
                    break
            
            return JsonResponse({
                'code': 0,
                'message': result['message'],
                'data': {
                    'port': port,
                    'status': 'connected'
                }
            })
        else:
            return JsonResponse({
                'code': 500,
                'message': result.get('error', 'Failed to stop acquisition')
            }, status=500)
        
    except Exception as e:
        return JsonResponse({
            'code': 500,
            'message': f'Failed to stop acquisition: {str(e)}'
        }, status=500)


@csrf_exempt
def disconnect_device(request, port=None):
    """断开设备连接
    
    POST /api/real-devices/{port}/disconnect/
    """
    if request.method != 'POST':
        return JsonResponse({
            'code': 405,
            'message': 'Method not allowed'
        }, status=405)
    
    try:
        if not port:
            return JsonResponse({
                'code': 400,
                'message': 'Port is required in URL path'
            }, status=400)
        
        # 断开连接
        result = disconnect_real_device(port)
        
        if result['success']:
            # 更新设备状态
            devices_list = get_all_devices()
            for device in devices_list:
                if device['type'] == 'wearable_eeg' and device.get('config', {}).get('port') == port:
                    update_device(device['id'], {
                        'config': {
                            **device.get('config', {}),
                            'connected': False,
                            'acquiring': False
                        }
                    })
                    break
            
            return JsonResponse({
                'code': 0,
                'message': result['message'],
                'data': {
                    'port': port,
                    'status': 'disconnected'
                }
            })
        else:
            return JsonResponse({
                'code': 500,
                'message': result.get('error', 'Failed to disconnect device')
            }, status=500)
        
    except Exception as e:
        return JsonResponse({
            'code': 500,
            'message': f'Failed to disconnect device: {str(e)}'
        }, status=500)


@csrf_exempt
def device_status(request, port=None):
    """获取设备状态
    
    GET /api/real-devices/status/ - 获取所有设备状态
    GET /api/real-devices/{port}/status/ - 获取单个设备状态
    """
    if request.method != 'GET':
        return JsonResponse({
            'code': 405,
            'message': 'Method not allowed'
        }, status=405)
    
    try:
        if port:
            # 获取单个设备状态
            result = get_device_status(port)
            
            if result['success']:
                return JsonResponse({
                    'code': 0,
                    'message': 'success',
                    'data': result['device']
                })
            else:
                return JsonResponse({
                    'code': 404,
                    'message': result.get('error', 'Device not found')
                }, status=404)
        else:
            # 获取所有设备状态
            result = get_all_connected_devices()
            
            return JsonResponse({
                'code': 0,
                'message': 'success',
                'data': {
                    'devices': result['devices'],
                    'count': len(result['devices'])
                }
            })
        
    except Exception as e:
        return JsonResponse({
            'code': 500,
            'message': f'Failed to get device status: {str(e)}'
        }, status=500)


@csrf_exempt
def real_devices(request):
    """真实设备管理主入口
    
    GET /api/real-devices/ - 获取所有真实设备信息
    """
    if request.method != 'GET':
        return JsonResponse({
            'code': 405,
            'message': 'Method not allowed'
        }, status=405)
    
    try:
        # 获取所有设备
        all_devices = get_all_devices()
        
        # 过滤出真实设备
        real_devices = []
        for device in all_devices:
            if device['type'] == 'wearable_eeg':
                # 获取设备连接状态
                port = device.get('config', {}).get('port')
                if port:
                    status_result = get_device_status(port)
                    if status_result['success']:
                        device['connection_status'] = status_result['device']
                    else:
                        device['connection_status'] = {
                            'port': port,
                            'status': 'disconnected',
                            'last_error': 'Not connected'
                        }
                else:
                    device['connection_status'] = {
                        'status': 'disconnected',
                        'last_error': 'No port configured'
                    }
                
                real_devices.append(device)
        
        return JsonResponse({
            'code': 0,
            'message': 'success',
            'data': {
                'devices': real_devices,
                'count': len(real_devices)
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'code': 500,
            'message': f'Failed to get real devices: {str(e)}'
        }, status=500)


@csrf_exempt
def debug_output(request):
    """获取串口调试输出（最近数据帧）

    GET /api/real-devices/debug-output/?port=/dev/ttyUSB0&count=200
    """
    if request.method != 'GET':
        return JsonResponse({
            'code': 405,
            'message': 'Method not allowed'
        }, status=405)

    try:
        port = request.GET.get('port')
        count = int(request.GET.get('count', '200'))
        if count < 1:
            count = 1
        if count > 2000:
            count = 2000

        result = get_debug_output(port=port, count=count)

        return JsonResponse({
            'code': 0,
            'message': 'success',
            'data': result
        })
    except Exception as e:
        return JsonResponse({
            'code': 500,
            'message': f'Failed to get debug output: {str(e)}'
        }, status=500)