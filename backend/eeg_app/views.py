import logging
logger = logging.getLogger(__name__)
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .graph_store import (
    get_graph,
    get_runtime_state,
    get_graph_revision,
    get_persisted_revision,
)
from .data_recorder import list_saved_files, get_active_recordings, get_file_path, start_recording, stop_recording
from .data_replay import list_replayable_files
from .python_node_templates import generate_python_prototype_spec, get_default_code_library
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
    """设备管理 API — 委托给 real_device_views.real_devices（统一数据源）。

    保留此路由仅为向后兼容，所有设备操作统一走 /api/real-devices/ 体系。
    """
    from . import real_device_views
    # 将 request 封装，添加 device_id 参数供下游使用
    request._device_id_override = device_id
    return real_device_views.real_devices(request)


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
    """GET /api/graph/ — 读取内存中的计算图（初始加载用）。

    图的修改通过 WebSocket ws/control/ 的 sync_graph 命令进行。
    """
    if request.method == 'GET':
        payload = dict(get_graph())
        payload['revision'] = get_graph_revision()
        payload['persistedRevision'] = get_persisted_revision()
        return JsonResponse(payload)
    return JsonResponse({'ok': False, 'error': 'Method not allowed. Use WebSocket ws/control/ sync_graph.'}, status=405)


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
    from .graph_store import get_output_nodes_for_recording

    if request.method == 'POST':
        output_nodes = get_output_nodes_for_recording()
        started = []
        errors = []
        for node in output_nodes:
            node_id = node.get('id')
            if not node_id:
                continue
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
