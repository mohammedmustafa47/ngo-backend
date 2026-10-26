"""Email, used for OTP codes (email verification and password reset).

Prints to the console unless EMAIL_HOST_USER / EMAIL_HOST_PASSWORD are set
(a Gmail App Password, not the account password), then sends via Gmail SMTP.
"""
from .env import ENV

EMAIL_HOST_USER = ENV.email_host_user
EMAIL_HOST_PASSWORD = ENV.email_host_password

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

DEFAULT_FROM_EMAIL = EMAIL_HOST_USER or 'no-reply@ngoauth.local'
