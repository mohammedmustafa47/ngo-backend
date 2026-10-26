"""Database connection (MySQL)."""
from .env import ENV

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'HOST': ENV.db_host,
        'PORT': str(ENV.db_port),
        'NAME': ENV.db_name,
        'USER': ENV.db_user,
        'PASSWORD': ENV.db_password,
    }
}
