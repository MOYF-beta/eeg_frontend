import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .graph_store import get_graph, run_graph, stop_graph, get_runtime_state, set_frozen, set_graph, validate_graph
from .data_recorder import list_saved_files, get_active_recordings, get_file_path
from .data_replay import list_replayable_files
from .python_node_templates import generate_python_prototype_spec, get_default_code_library


def health(request):
    return JsonResponse({'status': 'ok'})


@csrf_exempt
def devices(request, device_id=None):
    """设备管理API
    
    支持以下操作：
    - GET /api/devices/ - 获取所有设备
    - POST /api/devices/ - 创建设备
    - GET /api/devices/{device_id}/ - 获取单个设备
    - PATCH /api/devices/{device_id}/ - 更新设备
    - DELETE /api/devices/{device_id}/ - 删除设备
    """
    
    # 内存中存储设备（简化实现，实际项目应使用数据库）
    if not hasattr(devices, '_storage'):
        devices._storage = {
            'mock-1': {
                'id': 'mock-1',
                'name': '模拟设备 1',
                'alias': 'Test-1',
                'address': 'SIM-001',
                'type': 'simulated',
                'status': 'ready',
                'battery': 100,
                'sampling_rate': 1000,
                'channel_count': 8,
                'channels': ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8'],
                'config': {
                    'channels': [
                        {
                            'index': 0,
                            'wave_type': 'sine',
                            'frequency': 10,
                            'amplitude': 100,
                            'alias': 'CH1',
                            'noise_type': 'white',
                            'noise_amplitude': 5
                        }
                    ]
                },
                'created_at': '2026-02-19T10:00:00Z',
                'updated_at': '2026-02-19T10:00:00Z'
            }
        }
    
    if request.method == 'GET':
        if device_id:
            # 获取单个设备
            device = devices._storage.get(device_id)
            if not device:
                return JsonResponse({
                    'code': 404,
                    'message': f'Device {device_id} not found'
                }, status=404)
            
            return JsonResponse({
                'code': 0,
                'message': 'success',
                'data': device
            })
        else:
            # 获取所有设备
            return JsonResponse({
                'code': 0,
                'message': 'success',
                'data': list(devices._storage.values())
            })
    
    elif request.method == 'POST':
        # 创建设备
        try:
            data = json.loads(request.body)
            
            # 生成设备ID
            import time
            device_id = f'dev-{int(time.time() * 1000)}'
            
            # 创建设备对象
            new_device = {
                'id': device_id,
                'name': data.get('name', f'设备 {len(devices._storage) + 1}'),
                'alias': data.get('alias', ''),
                'address': data.get('address', 'SIM-001'),
                'type': data.get('type', 'simulated'),
                'status': 'ready',
                'battery': 100,
                'sampling_rate': data.get('sampling_rate', 250),
                'channel_count': data.get('channel_count', 8),
                'config': data.get('config', {}),
                'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'updated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }
            
            # 保存设备
            devices._storage[device_id] = new_device
            
            return JsonResponse({
                'code': 0,
                'message': 'Device created successfully',
                'data': {
                    'id': device_id,
                    'name': new_device['name'],
                    'status': 'ready'
                }
            }, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'code': 400,
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'Failed to create device: {str(e)}'
            }, status=500)
    
    elif request.method == 'PATCH':
        # 更新设备
        if not device_id:
            return JsonResponse({
                'code': 400,
                'message': 'Device ID is required'
            }, status=400)
        
        device = devices._storage.get(device_id)
        if not device:
            return JsonResponse({
                'code': 404,
                'message': f'Device {device_id} not found'
            }, status=404)
        
        try:
            data = json.loads(request.body)
            
            # 更新设备字段
            updatable_fields = ['name', 'alias', 'address', 'sampling_rate', 'channel_count', 'config']
            for field in updatable_fields:
                if field in data:
                    device[field] = data[field]
            
            # 更新更新时间
            import time
            device['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            
            return JsonResponse({
                'code': 0,
                'message': 'Device updated successfully',
                'data': device
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'code': 400,
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'Failed to update device: {str(e)}'
            }, status=500)
    
    elif request.method == 'DELETE':
        # 删除设备
        if not device_id:
            return JsonResponse({
                'code': 400,
                'message': 'Device ID is required'
            }, status=400)
        
        if device_id not in devices._storage:
            return JsonResponse({
                'code': 404,
                'message': f'Device {device_id} not found'
            }, status=404)
        
        # 删除设备
        del devices._storage[device_id]
        
        return JsonResponse({
            'code': 0,
            'message': 'Device deleted successfully'
        })
    
    else:
        return JsonResponse({
            'code': 405,
            'message': 'Method not allowed'
        }, status=405)


def saved_files(request):
    """获取已保存的数据文件列表"""
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    
    files = list_saved_files()
    return JsonResponse({'ok': True, 'files': files})


def replayable_files(request):
    """获取可回放的文件列表"""
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    
    files = list_replayable_files()
    return JsonResponse({'ok': True, 'files': files})


@csrf_exempt
def graph(request):
    if request.method == 'GET':
        return JsonResponse(get_graph())

    if request.method == 'POST':
        payload = json.loads(request.body or '{}')
        errors = validate_graph(payload)
        if errors:
            return JsonResponse({'ok': False, 'errors': errors}, status=400)
        set_graph(payload)
        return JsonResponse({'ok': True})

    return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)


@csrf_exempt
def graph_freeze(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    payload = json.loads(request.body or '{}')
    set_frozen(bool(payload.get('frozen', False)))
    return JsonResponse({'ok': True, 'frozen': get_graph().get('frozen', False)})


@csrf_exempt
def graph_run(request):
    if request.method == 'POST':
        payload = json.loads(request.body or '{}')
        mode = payload.get('mode', 'live')
        result = run_graph(mode=mode)
        if result.get('status') == 'error':
            return JsonResponse({'ok': False, 'error': result.get('error')}, status=400)
        return JsonResponse({'ok': True, 'result': result})
    if request.method == 'GET':
        return JsonResponse({'ok': True, 'state': get_runtime_state()})
    if request.method == 'DELETE':
        return JsonResponse({'ok': True, 'result': stop_graph()})
    return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)


@csrf_exempt
def graph_debug(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    try:
        payload = json.loads(request.body or '{}')
    except Exception:
        payload = {'error': 'invalid json'}
    # Print the payload to server terminal for debugging
    print('--- GRAPH DEBUG OUTPUT ---')
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except Exception:
        print(str(payload))
    print('--- END GRAPH DEBUG OUTPUT ---')
    return JsonResponse({'ok': True})


@csrf_exempt
def graph_python_prototype(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    payload = json.loads(request.body or '{}')
    input_count = payload.get('inputCount', 1)
    output_count = payload.get('outputCount', 1)
    function_name = payload.get('functionName')
    input_names = payload.get('inputNames')
    output_names = payload.get('outputNames')
    editable_code = payload.get('editableCode')

    spec = generate_python_prototype_spec(
        input_count=input_count,
        output_count=output_count,
        function_name=function_name,
        input_names=input_names,
        output_names=output_names,
        editable_code=editable_code,
    )
    return JsonResponse({'ok': True, **spec})


def graph_python_library(request):
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    return JsonResponse({'ok': True, 'library': get_default_code_library()})
