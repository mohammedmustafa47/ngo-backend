import logging

from django.conf import settings
from django.test import SimpleTestCase

from core.logging_redact import RedactFilter, redact


class RedactTests(SimpleTestCase):
    def test_password_key_masked(self):
        self.assertEqual(redact({'password': 'p', 'username': 'u'}), {'password': '***', 'username': 'u'})

    def test_nested_secret_masked(self):
        data = {'user': {'new_password': 'x'}, 'items': [{'refresh': 'r'}]}
        self.assertEqual(redact(data), {'user': {'new_password': '***'}, 'items': [{'refresh': '***'}]})

    def test_otp_and_code_keys_masked(self):
        self.assertEqual(redact({'otp': '4721', 'verification_code': '4721'}), {'otp': '***', 'verification_code': '***'})

    def test_pincode_not_masked(self):
        self.assertEqual(redact({'pincode': '581342', 'pickup_pincode': '581343'}), {'pincode': '581342', 'pickup_pincode': '581343'})

    def test_bearer_token_in_text(self):
        result = redact('Authorization: Bearer abc.def')
        self.assertIn('Bearer ***', result)
        self.assertNotIn('abc', result)

    def test_jwt_in_text(self):
        self.assertNotIn('eyJhbGc', redact('refreshed eyJhbGc.eyJzdWI.sig ok'))

    def test_otp_in_text(self):
        self.assertEqual(redact('otp=4721 sent'), 'otp=*** sent')

    def test_key_value_secrets_in_text(self):
        result = redact('login password=hunter2 ok, token: abc123xyz, refresh=opaque99')
        for secret in ('hunter2', 'abc123xyz', 'opaque99'):
            self.assertNotIn(secret, result)
        self.assertIn('login', result)

    def test_otp_written_as_words(self):
        self.assertNotIn('1234', redact('OTP is 1234'))

    def test_traceback_secret_redacted(self):
        try:
            raise ValueError('rejected password=hunter2')
        except ValueError:
            import sys
            record = logging.LogRecord('t', logging.ERROR, __file__, 1, 'failed', None, sys.exc_info())
        RedactFilter().filter(record)
        self.assertNotIn('hunter2', logging.Formatter().format(record))

    def test_filter_masks_record_args(self):
        record = logging.LogRecord('t', logging.INFO, __file__, 1, 'login %s', ({'password': 'p'},), None)
        self.assertTrue(RedactFilter().filter(record))
        message = record.getMessage()
        self.assertIn('***', message)
        self.assertNotIn("'p'", message)

    def test_logging_config_uses_the_filter(self):
        self.assertEqual(settings.LOGGING['handlers']['console']['filters'], ['redact'])
        self.assertEqual(settings.LOGGING['filters']['redact']['()'], 'core.logging_redact.RedactFilter')
