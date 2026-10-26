"""Mask secrets (passwords, tokens, OTP codes, session ids) before anything is logged."""
import logging
import re
from typing import Any, Mapping

MASK = '***'

# "code" and "otp" only count as whole words in a key, so "pincode" and "pickup_pincode" stay visible.
SECRET_KEY_RE = re.compile(
    r'password|passwd|secret|token|access|refresh|session|authorization|cookie|(^|_)(otp|code)($|_)',
    re.IGNORECASE,
)

TEXT_PATTERNS = (
    (re.compile(r'Bearer\s+\S+'), 'Bearer ' + MASK),
    (re.compile(r'eyJ[\w-]+\.[\w-]+\.[\w-]+'), MASK),
    (re.compile(r'\b(otp|code)\s*(?:[=:]|is)\s*\d{4}\b', re.IGNORECASE), r'\1=' + MASK),
    # "password=hunter2", "token: abc". Authorization is left to the Bearer pattern above.
    (re.compile(r'\b(password|passwd|secret|token|refresh|access)\b\s*[=:]\s*[^\s,;&]+', re.IGNORECASE), r'\1=' + MASK),
)


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: MASK if isinstance(key, str) and SECRET_KEY_RE.search(key) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return type(value)(redact(item) for item in value)
    if isinstance(value, str):
        for pattern, replacement in TEXT_PATTERNS:
            value = pattern.sub(replacement, value)
    return value


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.msg)
        if record.args:
            record.args = redact(record.args)
        if record.exc_info:
            # Format the traceback now so its text can be masked, then drop the raw exception.
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        elif record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True
