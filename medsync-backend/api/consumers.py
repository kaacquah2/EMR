"""
WebSocket consumer for real-time clinical alerts.
Clients subscribe by hospital ID; server broadcasts on alert create/resolve.
"""
import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class AlertConsumer(AsyncJsonWebsocketConsumer):
    """Subscribe to alerts for a hospital: ws://host/ws/alerts/<hospital_id>/"""

    async def connect(self):
        self.hospital_id = self.scope["url_route"]["kwargs"].get("hospital_id")
        if not self.hospital_id:
            await self.close(code=4000)
            return
        self.room_group_name = f"alerts_{self.hospital_id}"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if getattr(self, "room_group_name", None):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def alert_event(self, event):
        """Send alert payload to client."""
        await self.send(text_data=json.dumps(event.get("payload", {})))
