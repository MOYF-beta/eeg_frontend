import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .graph_store import get_graph, run_graph, set_frozen, set_graph, validate_graph
from .data_recorder import list_saved_files, get_active_recordings, get_file_path
from .data_replay import list_replayable_files


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
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    return JsonResponse({'ok': True, 'result': run_graph()})


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
