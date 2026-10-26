from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from NgoAuth.settings.env import load_env

VALID = {'DJANGO_SECRET_KEY': 'k', 'DB_PASSWORD': ''}


def problem_text(env):
    with_error = None
    try:
        load_env(env)
    except ImproperlyConfigured as exc:
        with_error = str(exc)
    return with_error


class LoadEnvTests(SimpleTestCase):
    def test_valid_minimal_env_uses_defaults(self):
        cfg = load_env(VALID)
        self.assertEqual(cfg.env, 'development')
        self.assertFalse(cfg.debug)
        self.assertEqual(cfg.allowed_hosts, ['localhost', '127.0.0.1'])
        self.assertEqual(cfg.db_port, 3306)
        self.assertEqual(cfg.cors_allowed_origins, ['http://localhost:8100', 'http://127.0.0.1:8100'])

    def test_missing_secret_key(self):
        text = problem_text({'DB_PASSWORD': ''})
        self.assertIn('DJANGO_SECRET_KEY', text)

    def test_invalid_django_env(self):
        self.assertIn('DJANGO_ENV', problem_text({**VALID, 'DJANGO_ENV': 'prod'}))

    def test_invalid_debug(self):
        self.assertIn('DJANGO_DEBUG', problem_text({**VALID, 'DJANGO_DEBUG': 'yes'}))

    def test_debug_is_case_insensitive(self):
        self.assertTrue(load_env({**VALID, 'DJANGO_DEBUG': 'True'}).debug)
        self.assertFalse(load_env({**VALID, 'DJANGO_DEBUG': 'FALSE'}).debug)

    def test_invalid_db_port(self):
        self.assertIn('DB_PORT', problem_text({**VALID, 'DB_PORT': '33o6'}))

    def test_missing_db_password_key(self):
        env = {'DJANGO_SECRET_KEY': 'k'}
        self.assertIn('DB_PASSWORD', problem_text(env))
        self.assertIsNone(problem_text({**env, 'DJANGO_ENV': 'test'}))

    def test_empty_db_password_allowed_when_key_present(self):
        self.assertEqual(load_env(VALID).db_password, '')

    def test_email_must_be_paired(self):
        self.assertIn('EMAIL_HOST_PASSWORD', problem_text({**VALID, 'EMAIL_HOST_USER': 'a@gmail.com'}))

    def test_bad_cors_origin(self):
        self.assertIn('CORS_ALLOWED_ORIGINS', problem_text({**VALID, 'CORS_ALLOWED_ORIGINS': 'localhost:8100'}))

    def test_values_are_trimmed(self):
        self.assertTrue(load_env({**VALID, 'DJANGO_DEBUG': ' True\r'}).debug)

    def test_repr_hides_secrets(self):
        cfg = load_env({
            'DJANGO_SECRET_KEY': 'secret-key-value',
            'DB_PASSWORD': 'db-password-value',
            'EMAIL_HOST_USER': 'a@gmail.com',
            'EMAIL_HOST_PASSWORD': 'mail-password-value',
        })
        for secret in ('secret-key-value', 'db-password-value', 'mail-password-value'):
            self.assertNotIn(secret, repr(cfg))

    def test_all_errors_reported_together(self):
        text = problem_text({'DB_PASSWORD': '', 'DB_PORT': 'x', 'DJANGO_DEBUG': 'maybe'})
        for name in ('DJANGO_SECRET_KEY', 'DB_PORT', 'DJANGO_DEBUG'):
            self.assertIn(name, text)
