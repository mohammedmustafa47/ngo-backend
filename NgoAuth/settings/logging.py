"""Logging: everything goes to the console through the redaction filter."""

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'redact': {'()': 'core.logging_redact.RedactFilter'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'filters': ['redact']},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    # Django's own logger gets the same handler (and stops propagating) so lines aren't printed twice.
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}
