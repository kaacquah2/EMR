"""WebSocket URL routing for Django Channels."""
from django.urls import path
from api.consumers import AlertConsumer

websocket_urlpatterns = [
    path("ws/alerts/<uuid:hospital_id>/", AlertConsumer.as_asgi()),
]
