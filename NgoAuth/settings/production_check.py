"""Production safety check: refuse to start with unsafe settings.

Only applies when DJANGO_ENV=production. Every problem is reported together.
"""
from typing import Any, Mapping

from django.core.exceptions import ImproperlyConfigured

MIN_KEY_LENGTH = 50
MIN_KEY_UNIQUE_CHARS = 5
INSECURE_KEY_PREFIX = 'django-insecure-'


def find_problems(s: Mapping[str, Any]) -> list:
    if s['ENV'].env != 'production':
        return []

    problems = []

    if s['DEBUG']:
        problems.append('DEBUG is on. Set DJANGO_DEBUG=false.')

    key = s['SECRET_KEY']
    if len(key) < MIN_KEY_LENGTH or len(set(key)) < MIN_KEY_UNIQUE_CHARS or key.startswith(INSECURE_KEY_PREFIX):
        problems.append(
            f'SECRET_KEY is weak. Use a random key of at least {MIN_KEY_LENGTH} characters '
            f'(not one starting with "{INSECURE_KEY_PREFIX}").'
        )

    hosts = s['ALLOWED_HOSTS']
    if not hosts or '*' in hosts:
        problems.append('ALLOWED_HOSTS is empty or contains "*". List your real domain(s) in DJANGO_ALLOWED_HOSTS.')

    for name in ('SESSION_COOKIE_SECURE', 'CSRF_COOKIE_SECURE'):
        if not s.get(name):
            problems.append(f'{name} is off. Cookies must be secure in production.')

    if s.get('CORS_ALLOW_ALL_ORIGINS'):
        problems.append('CORS_ALLOW_ALL_ORIGINS is on. List the allowed origins in CORS_ALLOWED_ORIGINS instead.')

    return problems


def check(s: Mapping[str, Any]) -> None:
    problems = find_problems(s)
    if problems:
        raise ImproperlyConfigured('Refusing to start in production:\n' + '\n'.join(f'- {p}' for p in problems))
