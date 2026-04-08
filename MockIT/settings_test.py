"""Test settings — uses SQLite to avoid PostgreSQL version dependency."""

from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

Q_CLUSTER = {
    'sync': True,
    'orm': 'default',
}
