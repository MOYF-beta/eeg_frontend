from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health),
    path('devices/', views.devices),
    path('graph/', views.graph),
    path('graph/freeze/', views.graph_freeze),
    path('graph/run/', views.graph_run),
    path('graph/debug/', views.graph_debug),
    path('saved-files/', views.saved_files),
    path('replayable-files/', views.replayable_files),
]
