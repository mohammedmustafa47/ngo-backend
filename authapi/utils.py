from django.core.mail import send_mail
from django.conf import settings

from .models import OTP


def create_otp(email, purpose):
    """Invalidate any previous unused OTPs for this email/purpose and create a new one."""
    OTP.objects.filter(email=email, purpose=purpose, is_used=False).update(is_used=True)
    otp = OTP.objects.create(email=email, code=OTP.generate_code(), purpose=purpose)
    return otp


def send_otp_email(email, code, purpose):
    if purpose == 'verify_email':
        subject = 'Verify your email'
        message = f'Your email verification code is {code}. It expires in 10 minutes.'
    else:
        subject = 'Reset your password'
        message = f'Your password reset code is {code}. It expires in 10 minutes.'

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )
