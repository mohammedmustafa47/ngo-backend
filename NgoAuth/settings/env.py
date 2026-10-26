"""Environment: the only module that reads the environment, and it checks everything.

`load_env` collects every problem and raises one ImproperlyConfigured listing them all,
so a broken .env is fixed in a single pass instead of one error at a time.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

__all__ = ['BASE_DIR', 'ENV']

BASE_DIR = Path(__file__).resolve().parent.parent.parent

ENVIRONMENTS = ('development', 'test', 'production')
DEFAULT_CORS_ORIGINS = 'http://localhost:8100,http://127.0.0.1:8100'


@dataclass(frozen=True)
class EnvConfig:
    """Validated settings. Secret fields are excluded from repr so printing settings never leaks them."""
    env: str
    secret_key: str = field(repr=False)
    debug: bool
    allowed_hosts: list
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str = field(repr=False)
    email_host_user: str
    email_host_password: str = field(repr=False)
    cors_allowed_origins: list


def _get(environ: Mapping[str, str], key: str, default: str = '') -> str:
    return str(environ.get(key, default)).strip()


def _split(value: str) -> list:
    return [item.strip() for item in value.split(',') if item.strip()]


def load_env(environ: Mapping[str, str]) -> EnvConfig:
    problems = []

    env = _get(environ, 'DJANGO_ENV', 'development') or 'development'
    if env not in ENVIRONMENTS:
        problems.append(f'DJANGO_ENV must be one of {", ".join(ENVIRONMENTS)} (got "{env}").')

    secret_key = _get(environ, 'DJANGO_SECRET_KEY')
    if not secret_key:
        problems.append('DJANGO_SECRET_KEY is not set. Add it to the .env file next to manage.py.')

    debug_raw = _get(environ, 'DJANGO_DEBUG', 'false').lower()
    if debug_raw not in ('true', 'false'):
        problems.append(f'DJANGO_DEBUG must be true or false (got "{debug_raw}").')

    port_raw = _get(environ, 'DB_PORT', '3306')
    try:
        db_port = int(port_raw)
    except ValueError:
        db_port = 3306
        problems.append(f'DB_PORT must be a number (got "{port_raw}").')

    if 'DB_PASSWORD' not in environ and env != 'test':
        problems.append('DB_PASSWORD is not set. Add DB_PASSWORD= (it may be empty for a passwordless local database).')

    email_user = _get(environ, 'EMAIL_HOST_USER')
    email_password = _get(environ, 'EMAIL_HOST_PASSWORD')
    if bool(email_user) != bool(email_password):
        problems.append('EMAIL_HOST_USER and EMAIL_HOST_PASSWORD must be set together or both left empty.')

    cors = _split(_get(environ, 'CORS_ALLOWED_ORIGINS', DEFAULT_CORS_ORIGINS))
    for origin in cors:
        if not origin.startswith(('http://', 'https://')):
            problems.append(f'CORS_ALLOWED_ORIGINS entries must start with http:// or https:// (got "{origin}").')

    if problems:
        raise ImproperlyConfigured('Invalid environment configuration:\n' + '\n'.join(f'- {p}' for p in problems))

    return EnvConfig(
        env=env,
        secret_key=secret_key,
        debug=debug_raw == 'true',
        allowed_hosts=_split(_get(environ, 'DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')),
        db_host=_get(environ, 'DB_HOST', 'localhost'),
        db_port=db_port,
        db_name=_get(environ, 'DB_NAME', 'ngoauth'),
        db_user=_get(environ, 'DB_USER', 'root'),
        db_password=_get(environ, 'DB_PASSWORD'),
        email_host_user=email_user,
        email_host_password=email_password,
        cors_allowed_origins=cors,
    )


load_dotenv(BASE_DIR / '.env')

ENV = load_env(os.environ)
