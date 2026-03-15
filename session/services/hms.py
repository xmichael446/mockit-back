import time
import uuid
import jwt
import requests
from django.conf import settings


def generate_management_token():
    now = int(time.time())
    payload = {
        "access_key": settings.HMS_APP_ACCESS_KEY,
        "type": "management",
        "version": 2,
        "jti": str(uuid.uuid4()),
        "iat": now - 300,
        "nbf": now - 300,
        "exp": now + 86400,
    }
    return jwt.encode(payload, settings.HMS_APP_SECRET, algorithm="HS256")


def create_room(session_id):
    token = generate_management_token()
    response = requests.post(
        "https://api.100ms.live/v2/rooms",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": f"mock-session-{session_id}-{uuid.uuid4().hex[:8]}",
            "template_id": settings.HMS_TEMPLATE_ID,
            "region": "eu",
        },
    )
    if not response.ok:
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        raise Exception(f"100ms API error {response.status_code}: {detail}")
    return response.json()["id"]


def generate_app_token(room_id, user_id, role):
    now = int(time.time())
    payload = {
        "access_key": settings.HMS_APP_ACCESS_KEY,
        "type": "app",
        "version": 2,
        "room_id": room_id,
        "user_id": str(user_id),
        "role": role,
        "jti": str(uuid.uuid4()),
        "iat": now - 300,
        "nbf": now - 300,
        "exp": now + 3600,  # 1 hour — sufficient for any IELTS mock session
    }
    return jwt.encode(payload, settings.HMS_APP_SECRET, algorithm="HS256")
