from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase


class HealthTests(TestCase):
    def test_health_ok(self):
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'database': 'ok'})

    def test_database_down_returns_503_without_details(self):
        with patch('core.health.connection') as connection, self.assertLogs('core.health', level='ERROR'):
            connection.cursor.side_effect = OperationalError('boom')
            response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'degraded', 'database': 'error'})
        self.assertNotIn('boom', response.content.decode())

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post('/api/health').status_code, 405)

    def test_no_auth_needed(self):
        response = self.client.get('/api/health', HTTP_AUTHORIZATION='Bearer invalid')
        self.assertEqual(response.status_code, 200)
