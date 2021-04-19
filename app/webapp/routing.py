from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/brat/$', consumers.BratConsumer.as_asgi()),
]

channel_consumers = {
    "worker-manager": consumers.WorkerConsumer.as_asgi(),
}
