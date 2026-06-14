import os
from django.contrib import admin
from django.urls import include, path, re_path
from django.conf import settings
from django.views.static import serve
from django.http import FileResponse

def frontend_index(request):
    """SPA 入口：返回前端 index.html"""
    index_path = settings.FRONTEND_DIST_DIR / 'index.html'
    return FileResponse(open(index_path, 'rb'))

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('eeg_app.urls')),
    # 托管前端 assets 静态资源
    path('assets/<path:path>', serve, {
        'document_root': settings.FRONTEND_DIST_DIR / 'assets',
    }),
    # SPA 兜底：所有非 api/admin 路径返回 index.html
    re_path(r'^(?!api/|admin/).*$', frontend_index),
]
