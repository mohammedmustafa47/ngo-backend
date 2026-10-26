from types import SimpleNamespace

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from NgoAuth.settings.production_check import check, find_problems

STRONG_KEY = ''.join(chr(65 + i % 26) + str(i % 10) for i in range(30))  # 60 chars, many distinct


def safe(**overrides):
    settings = {
        'ENV': SimpleNamespace(env='production'),
        'SECRET_KEY': STRONG_KEY,
        'DEBUG': False,
        'ALLOWED_HOSTS': ['api.food4u.in'],
        'SESSION_COOKIE_SECURE': True,
        'CSRF_COOKIE_SECURE': True,
        'CORS_ALLOW_ALL_ORIGINS': False,
    }
    settings.update(overrides)
    return settings


class ProductionCheckTests(SimpleTestCase):
    def assertOneProblem(self, name, **overrides):
        problems = find_problems(safe(**overrides))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn(name, problems[0])

    def test_safe_production_passes(self):
        self.assertEqual(find_problems(safe()), [])

    def test_non_production_is_never_checked(self):
        unsafe = safe(ENV=SimpleNamespace(env='development'), DEBUG=True, ALLOWED_HOSTS=['*'])
        self.assertEqual(find_problems(unsafe), [])

    def test_debug_on_refused(self):
        self.assertOneProblem('DEBUG', DEBUG=True)

    def test_short_key_refused(self):
        self.assertOneProblem('SECRET_KEY', SECRET_KEY='abc123')

    def test_low_variety_key_refused(self):
        self.assertOneProblem('SECRET_KEY', SECRET_KEY='a' * 60)

    def test_insecure_prefix_refused(self):
        self.assertOneProblem('SECRET_KEY', SECRET_KEY='django-insecure-' + STRONG_KEY)

    def test_wildcard_host_refused(self):
        self.assertOneProblem('ALLOWED_HOSTS', ALLOWED_HOSTS=['*'])

    def test_empty_hosts_refused(self):
        self.assertOneProblem('ALLOWED_HOSTS', ALLOWED_HOSTS=[])

    def test_insecure_session_cookie_refused(self):
        self.assertOneProblem('SESSION_COOKIE_SECURE', SESSION_COOKIE_SECURE=False)

    def test_insecure_csrf_cookie_refused(self):
        self.assertOneProblem('CSRF_COOKIE_SECURE', CSRF_COOKIE_SECURE=False)

    def test_cors_allow_all_refused(self):
        self.assertOneProblem('CORS_ALLOW_ALL_ORIGINS', CORS_ALLOW_ALL_ORIGINS=True)

    def test_check_raises_with_all_problems(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            check(safe(DEBUG=True, ALLOWED_HOSTS=['*']))
        message = str(ctx.exception)
        self.assertIn('DEBUG', message)
        self.assertIn('ALLOWED_HOSTS', message)
