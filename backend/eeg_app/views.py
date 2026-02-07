from django.http import JsonResponse


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
