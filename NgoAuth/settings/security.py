"""Security: secret key, debug flag, hosts and CORS."""
from .env import ENV

SECRET_KEY = ENV.secret_key

DEBUG = ENV.debug

ALLOWED_HOSTS = ENV.allowed_hosts

CORS_ALLOWED_ORIGINS = ENV.cors_allowed_origins

# Any origin is allowed only while DEBUG is on; otherwise only CORS_ALLOWED_ORIGINS above.
CORS_ALLOW_ALL_ORIGINS = DEBUG

# Cookies are secure in production only; development runs over plain http (browser and Android app).
SESSION_COOKIE_SECURE = ENV.env == 'production'
CSRF_COOKIE_SECURE = ENV.env == 'production'
if ENV.env == 'production':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
