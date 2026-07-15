import logging
logger = logging.getLogger(__name__)
import json
import time

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .graph_store import (
    get_graph,
    run_graph,
    stop_graph,
    get_runtime_state,
    set_frozen,
    set_graph,
    validate_graph,
    persist_graph,
    get_graph_revision,
    get_persisted_revision,
    apply_graph_sync,
)
from .data_recorder import list_saved_files, get_active_recordings, get_file_path, start_recording, stop_recording
from .data_replay import list_replayable_files
from .python_node_templates import generate_python_prototype_spec, get_default_code_library
from .device_store import get_all_devices, create_device, update_device, delete_device
from .graph_sync import broadcast_graph_state
from .perf_monitor import get_perf_monitor


def health(request):
    return JsonResponse({'status': 'ok'})


def status(request):
    """返回系统性能指标"""
    monitor = get_perf_monitor()
    data = {'ok': True, **monitor.snapshot()}
    # 附加计算图运行时状态
    runtime = get_runtime_state()
    data['runtime'] = {
        'running': runtime.get('running', False),
        'mode': runtime.get('mode', 'live'),
        'frozen': runtime.get('frozen', False),
        'processingDelayMs': runtime.get('processingDelayMs', 0),
    }
    return JsonResponse(data)


@csrf_exempt
def devices(request, device_id=None):
    """设备管理API
    
    支持以下操作：
    - GET /api/devices/ - 获取所有设备
    - POST /api/devices/ - 创建设备
    - GET /api/devices/{device_id}/ - 获取单个设备
    - PATCH /api/devices/{device_id}/ - 更新设备
    - DELETE /api/devices/{device_id}/ - 删除设备
    
    统一响应格式: {ok: bool, data?: any, error?: string}
    """
    
    if request.method == 'GET':
        if device_id:
            # 获取单个设备
            devices_list = get_all_devices()
            device = next((d for d in devices_list if d['id'] == device_id), None)
            if not device:
                return JsonResponse({
                    'ok': False, 'error': f'Device {device_id} not found'
                }, status=404)
            
            return JsonResponse({'ok': True, 'data': device})
        else:
            # 获取所有设备
            devices_list = get_all_devices()
            return JsonResponse({'ok': True, 'data': devices_list})
    
    elif request.method == 'POST':
        # 创建设备
        try:
            data = json.loads(request.body)
            device = create_device(data)
            return JsonResponse({
                'ok': True,
                'data': {
                    'id': device['id'],
                    'name': device['name'],
                    'status': 'ready'
                }
            }, status=201)
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f'Failed to create device: {str(e)}'}, status=500)
    
    elif request.method == 'PATCH':
        # 更新设备
        if not device_id:
            return JsonResponse({'ok': False, 'error': 'Device ID is required'}, status=400)
        
        try:
            data = json.loads(request.body)
            
            # 检查计算图是否正在运行
            runtime_state = get_runtime_state()
            if runtime_state.get('running'):
                return JsonResponse({
                    'ok': False, 'error': 'Cannot modify devices while graph is running'
                }, status=403)
            
            # 更新设备
            device = update_device(device_id, data)
            if not device:
                return JsonResponse({
                    'ok': False, 'error': f'Device {device_id} not found'
                }, status=404)
            
            return JsonResponse({'ok': True, 'data': device})
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'Invalid JSON data'}, status=400)
        except ValueError as e:
            return JsonResponse({'ok': False, 'error': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f'Failed to update device: {str(e)}'}, status=500)
    
    elif request.method == 'DELETE':
        # 删除设备
        if not device_id:
            return JsonResponse({'ok': False, 'error': 'Device ID is required'}, status=400)
        try:
            # 检查计算图是否正在运行
            runtime_state = get_runtime_state()
            if runtime_state.get('running'):
                return JsonResponse({
                    'ok': False, 'error': 'Cannot delete devices while graph is running'
                }, status=403)
            
            # 删除设备
            success = delete_device(device_id)
            if not success:
                return JsonResponse({
                    'ok': False, 'error': f'Device {device_id} not found'
                }, status=404)
            
            return JsonResponse({'ok': True})
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f'Failed to delete device: {str(e)}'}, status=500)
    
    else:
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)


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
        payload = dict(get_graph())
        payload['revision'] = get_graph_revision()
        payload['persistedRevision'] = get_persisted_revision()
        return JsonResponse(payload)

    if request.method == 'POST':
        try:
            payload = json.loads(request.body or '{}')
            errors = validate_graph(payload)
            if errors:
                return JsonResponse({'ok': False, 'errors': errors}, status=400)
            
            # 检查计算图是否正在运行
            runtime_state = get_runtime_state()
            if runtime_state.get('running'):
                return JsonResponse({
                    'ok': False, 
                    'errors': ['Cannot save graph while it is running']
                }, status=403)
            
            result = apply_graph_sync(payload, base_revision=payload.get('baseRevision'))
            if result.get('conflict'):
                return JsonResponse(result, status=409)
            broadcast_graph_state(reason='synced')
            return JsonResponse(result)
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'errors': ['Invalid JSON']}, status=400)
        except RuntimeError as e:
            return JsonResponse({'ok': False, 'errors': [str(e)]}, status=403)

    return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)


@csrf_exempt
def graph_sync(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'errors': ['Invalid JSON']}, status=400)

    errors = validate_graph(payload)
    if errors:
        return JsonResponse({'ok': False, 'errors': errors}, status=400)

    try:
        result = apply_graph_sync(payload, base_revision=payload.get('baseRevision'))
        if result.get('conflict'):
            return JsonResponse(result, status=409)
        broadcast_graph_state(reason='synced')
        return JsonResponse(result)
    except RuntimeError as e:
        return JsonResponse({'ok': False, 'errors': [str(e)]}, status=403)


@csrf_exempt
def graph_save(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    try:
        result = persist_graph()
        broadcast_graph_state(reason='persisted')
        return JsonResponse({'ok': True, **result})
    except Exception as e:
        return JsonResponse({'ok': False, 'errors': [str(e)]}, status=500)


@csrf_exempt
def graph_freeze(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    payload = json.loads(request.body or '{}')
    set_frozen(bool(payload.get('frozen', False)))
    broadcast_graph_state(reason='freeze_changed')
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
    logger.debug('--- GRAPH DEBUG OUTPUT ---')
    try:
        logger.debug(json.dumps(payload, ensure_ascii=False, indent=2))
    except Exception:
        logger.debug(str(payload))
    logger.debug('--- END GRAPH DEBUG OUTPUT ---')
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

@csrf_exempt
def graph_record(request):
    """全局录制控制 - 录制所有输出节点的数据
    
    POST: 开始录制所有输出节点
    DELETE: 停止所有录制
    """
    from .data_recorder import start_recording, stop_recording, get_active_recordings
    from .graph_store import get_graph

    if request.method == 'POST':
        graph = get_graph()
        nodes = graph.get('nodes', []) or []
        started = []
        errors = []
        for node in nodes:
            node_type = str(node.get('type') or '').upper()
            node_id = node.get('id')
            if not node_id:
                continue
            # 录制所有输出节点 (OSC)
            if node_type == 'OSC':
                params = node.get('params', {}) or {}
                filename = params.get('filename')
                result = start_recording(
                    node_id=node_id,
                    filename=filename,
                    format='CSV',
                )
                if result.get('ok'):
                    started.append({'nodeId': node_id, 'filepath': result.get('filepath')})
                else:
                    errors.append({'nodeId': node_id, 'error': result.get('error')})

        return JsonResponse({
            'ok': True,
            'recording': True,
            'started': started,
            'errors': errors if errors else None,
        })

    if request.method == 'DELETE':
        active = get_active_recordings()
        stopped = []
        for rec in active:
            result = stop_recording(rec['nodeId'])
            if result.get('ok'):
                stopped.append(result)
        return JsonResponse({
            'ok': True,
            'recording': False,
            'stopped': stopped,
        })

    return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
