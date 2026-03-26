# Testing Patterns

**Analysis Date:** 2026-03-27

## Test Framework

**Runner:**
- Django TestCase (built-in, no explicit framework config)
- Testing dependencies: none explicitly listed in `requirements.txt`
- Default: `python manage.py test` (unittest runner)

**Assertion Library:**
- Python unittest assertions (default Django testing)

**Run Commands:**
```bash
python manage.py test                                    # Run all tests
python manage.py test session.tests.TestClassName       # Run specific test class
python manage.py test session.tests.TestClassName.test_method  # Run single test
python manage.py test --keepdb                          # Keep test database between runs
```

## Test File Organization

**Location:**
- Co-located with app code: `<app>/tests.py` (one per Django app)
- Current test files:
  - `main/tests.py` — auth and user tests
  - `questions/tests.py` — question bank tests
  - `session/tests.py` — session lifecycle tests

**Naming:**
- Test files: `tests.py` (Django convention)
- Test classes: `TestClassName(TestCase)`
- Test methods: `test_method_description()`

**Structure:**
```
app/
├── models.py
├── views.py
├── serializers.py
├── tests.py          # All tests for this app
├── urls.py
└── services/
    └── hms.py
```

## Test Structure

**Suite Organization:**
Current test files are mostly empty (boilerplate only):

```python
from django.test import TestCase

# Create your tests here.
```

**Recommended Test Class Pattern (from Django conventions):**
```python
from django.test import TestCase
from main.models import User

class UserModelTests(TestCase):
    def setUp(self):
        """Set up test data before each test."""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            role=User.Role.EXAMINER
        )

    def tearDown(self):
        """Clean up after each test."""
        self.user.delete()

    def test_user_creation(self):
        """Test that user is created correctly."""
        self.assertTrue(self.user.is_active)
        self.assertEqual(self.user.role, User.Role.EXAMINER)
```

**Patterns:**
- `setUp()` — called before each test; create test data, mock dependencies
- `tearDown()` — called after each test; clean up resources
- `TestCase.client` — built-in test client for HTTP requests
- `TestCase.assertXXX()` — standard unittest assertions

## Test Types

**Unit Tests (Current Gap):**
- Scope: Test individual models, serializers, utility functions in isolation
- Approach: Create model instances, call methods, assert results
- File locations: `session/tests.py`, `main/tests.py`, `questions/tests.py`
- Example targets:
  - `models.py`: `TimestampedModel.created_at`, `User.__str__()`, `EmailVerificationToken.is_expired`, `IELTSMockSession.duration`
  - `services/hms.py`: `generate_management_token()`, `create_room()`, `generate_app_token()`
  - `serializers.py`: Validation methods like `validate_part_1()`, `MockPresetCreateSerializer.create()`

**Integration Tests (Current Gap):**
- Scope: Test REST endpoints with database interactions
- Approach: Use `TestCase` with test database, make requests via `self.client`, verify database state
- File locations: `session/tests.py` (for REST views), `main/tests.py` (for auth views)
- Example targets:
  - `SessionListCreateView.get()` — filter by status, verify serialization
  - `StartSessionView.post()` — create room, broadcast event, verify state
  - `AcceptInviteView.post()` — assign candidate, trigger broadcast

**WebSocket Tests (Not Implemented):**
- Framework: `channels.testing.WebsocketCommunicator` (available in channels)
- File location: `session/tests.py`
- Example target: `SessionConsumer` authentication, group join, event relay
- Pattern (from channels docs):
  ```python
  from channels.testing import WebsocketCommunicator
  from session.consumers import SessionConsumer

  async def test_consumer_connect():
      communicator = WebsocketCommunicator(SessionConsumer.as_asgi(), "ws/session/1/?token=valid_token")
      connected, subprotocol = await communicator.connect()
      assert connected
      await communicator.disconnect()
  ```

**E2E Tests:**
- Not implemented
- Selenium or Playwright would be needed for full browser testing
- Out of scope for Django backend testing

## Mocking

**Framework:**
- `unittest.mock` (Python standard library)
- `unittest.mock.patch` for mocking external calls

**Patterns (Recommended):**
```python
from unittest.mock import patch, MagicMock

# Mock external API call in service layer
@patch('session.services.hms.requests.post')
def test_create_room_success(mock_post):
    mock_post.return_value.ok = True
    mock_post.return_value.json.return_value = {"id": "room-123"}

    room_id = create_room(session_id=1)
    assert room_id == "room-123"
    mock_post.assert_called_once()

# Mock token authentication
@patch('rest_framework.authtoken.models.Token.objects.get')
def test_consumer_authentication(mock_token_get):
    mock_token_get.return_value = MagicMock(user=user_instance)
    # test consumer auth
```

**What to Mock:**
- External API calls: `100ms API` in `session/services/hms.py`
- Email sending: `send_verification_email()` in `main/services/email.py`
- Token lookups: `Token.objects.get()` in consumer authentication
- Database queries for performance testing

**What NOT to Mock:**
- Django ORM model operations (use test database instead)
- Serializer validation (test with real validation logic)
- Django template rendering
- REST framework permission checks

## Fixtures and Factories

**Test Data (Recommended Pattern):**
```python
# In tests.py or separate fixtures file
from main.models import User
from questions.models import Topic, Question
from session.models import IELTSMockSession, MockPreset

class BaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Create shared test data once per test class."""
        cls.examiner = User.objects.create_user(
            username='examiner',
            password='pass',
            role=User.Role.EXAMINER
        )
        cls.candidate = User.objects.create_user(
            username='candidate',
            password='pass',
            role=User.Role.CANDIDATE
        )
        cls.topic = Topic.objects.create(
            name='Weather',
            slug='weather',
            part=1
        )
        cls.preset = MockPreset.objects.create(
            owner=cls.examiner,
            name='Standard Preset'
        )
        cls.session = IELTSMockSession.objects.create(
            examiner=cls.examiner,
            preset=cls.preset
        )
```

**Location:**
- In app `tests.py` files, or
- In separate `tests/factories.py` for large test suites

## Coverage

**Requirements:**
- No coverage requirement enforced (no `.coveragerc` or pytest config detected)
- Recommended: Aim for >70% on critical paths (auth, session lifecycle)

**View Coverage (Recommended):**
```bash
coverage run --source='.' manage.py test
coverage report
coverage html  # Generate HTML report in htmlcov/
```

## Async Testing

**Pattern for Async Views/Consumers:**
```python
from django.test import AsyncTestCase
from channels.testing import WebsocketCommunicator
import asyncio

class SessionConsumerTests(AsyncTestCase):
    async def test_consumer_receive_ping(self):
        communicator = WebsocketCommunicator(SessionConsumer.as_asgi(), "ws/session/1/?token=token")
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        await communicator.send_json_to({"type": "ping"})
        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], "pong")

        await communicator.disconnect()
```

## Error Testing

**Pattern for Exception Handling:**
```python
def test_invalid_invite_token(self):
    """Test that invalid invite tokens are rejected."""
    response = self.client.post('/api/sessions/accept-invite/', {
        'invite_token': 'invalid'
    })
    self.assertEqual(response.status_code, 400)
    self.assertIn('Invalid invite token', response.data['invite_token'][0])

def test_create_room_api_failure(self):
    """Test graceful handling of 100ms API errors."""
    with patch('session.services.hms.requests.post') as mock_post:
        mock_post.return_value.ok = False
        mock_post.return_value.status_code = 500
        mock_post.return_value.json.return_value = {"error": "Internal error"}

        with self.assertRaises(Exception) as context:
            create_room(session_id=1)
        self.assertIn("100ms API error", str(context.exception))
```

## Critical Test Gaps

**Currently Untested:**
- All REST views in `session/views.py` (1000+ lines)
- All serializer validation in `session/serializers.py`
- WebSocket consumer authentication and event relay (`session/consumers.py`)
- Email verification flow (`main/views.py` + `main/services/email.py`)
- Permission checks (`main/permissions.py`)
- Model properties and methods (duration calculations, band scoring)
- 100ms integration (`session/services/hms.py`)

**High Priority for Addition:**
1. Session lifecycle: create → start → join → end
2. Invite token validation and acceptance
3. Score calculation and result release
4. WebSocket authentication and broadcast
5. Permission enforcement (examiner-only, candidate-only operations)

---

*Testing analysis: 2026-03-27*
