"""Cache. Also backs DRF throttling (the OTP and password-reset rate limits)."""

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
