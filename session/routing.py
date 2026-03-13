from django.urls import re_path

from .consumers import SessionConsumer

websocket_urlpatterns = [
    re_path(r"^ws/session/(?P<session_id>\d+)/$", SessionConsumer.as_asgi()),
]
