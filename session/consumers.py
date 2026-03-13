import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.models import Q


class SessionConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for a live IELTS mock session.

    Connect: ws://host/ws/session/<session_id>/?token=<auth_token>

    The consumer:
      - Authenticates the user via DRF token passed as query param
      - Verifies the user is a participant (examiner or candidate) of the session
      - Joins the session-scoped channel group "session_<session_id>"
      - Forwards all server-initiated events to the WebSocket client
      - Clients may send {"type": "ping"} to keep the connection alive

    Events are broadcast from REST views via channel_layer.group_send().
    """

    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.group_name = f"session_{self.session_id}"

        user = await self._authenticate()
        if user is None:
            await self.close(code=4001)
            return

        is_participant = await self._is_participant(user)
        if not is_participant:
            await self.close(code=4003)
            return

        self.user = user
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            msg = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            return
        if msg.get("type") == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))

    # ── Channel layer event handler ───────────────────────────────────────────
    # REST views call:
    #   async_to_sync(channel_layer.group_send)(group_name, {"type": "session_event", "data": {...}})
    # Channels routes "session_event" → this method.

    async def session_event(self, event):
        await self.send(text_data=json.dumps(event["data"]))

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _authenticate(self):
        qs = self.scope.get("query_string", b"").decode()
        token_key = None
        for part in qs.split("&"):
            if part.startswith("token="):
                token_key = part[6:]
                break
        if not token_key:
            return None
        return await self._get_user_from_token(token_key)

    @database_sync_to_async
    def _get_user_from_token(self, token_key):
        from rest_framework.authtoken.models import Token
        try:
            token = Token.objects.select_related("user").get(key=token_key)
            return token.user
        except Token.DoesNotExist:
            return None

    @database_sync_to_async
    def _is_participant(self, user):
        from .models import IELTSMockSession
        return IELTSMockSession.objects.filter(
            pk=self.session_id
        ).filter(
            Q(examiner=user) | Q(candidate=user)
        ).exists()
