"""Health check: confirms the app is up and the database answers."""
import logging

from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except DatabaseError:
        logger.exception('Health check: database did not answer')
        return JsonResponse({'status': 'degraded', 'database': 'error'}, status=503)
    return JsonResponse({'status': 'ok', 'database': 'ok'})
