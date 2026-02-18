import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .graph_store import get_graph, run_graph, stop_graph, get_runtime_state, set_frozen, set_graph, validate_graph
from .data_recorder import list_saved_files, get_active_recordings, get_file_path
from .data_replay import list_replayable_files
from .python_node_templates import generate_python_prototype_spec, get_default_code_library


def health(request):
    return JsonResponse({'status': 'ok'})


def devices(request):
    return JsonResponse({
        'devices': [
            {
                'id': 'mock-1',
                'name': '模拟设备 1',
                'address': 'COM3',
                'channels': ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8'],
            }
        ]
    })


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
