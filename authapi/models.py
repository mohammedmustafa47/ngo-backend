import random
from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import timedelta

# Create your models here.


class Area(models.Model):
    """A geographic zone (e.g. a town) with its own Area Admin, donors,
    and volunteers. Matched at signup by pincode."""

    name = models.CharField(max_length=100, unique=True)
    pincodes = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    # Define role choices
    ROLES = (
        ('super_admin', 'Super Admin'),
        ('admin', 'Area Admin'),
        ('donor', 'Donor'),
        ('volunteer', 'Volunteer'),
    )

    # Add role field with choices
    role = models.CharField(max_length=15, choices=ROLES,default= 'donor')
    is_email_verified = models.BooleanField(default=False)
    pincode = models.CharField(max_length=10, blank=True)
    area = models.ForeignKey(
        'Area', on_delete=models.SET_NULL, null=True, blank=True, related_name='users'
    )

    class Meta:
        ordering = ['id']

    # def __str__(self):
    #     return self.username


class OTP(models.Model):
    PURPOSE_CHOICES = (
        ('verify_email', 'Verify Email'),
        ('reset_password', 'Reset Password'),
    )

    email = models.EmailField()
    code = models.CharField(max_length=4)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    is_used = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=10)

    @staticmethod
    def generate_code():
        return f"{random.randint(0, 9999):04d}"

    def __str__(self):
        return f"{self.email} - {self.purpose} - {self.code}"


class Role(models.Model):
    name=models.CharField(max_length=200,unique=True)

    def __str__(self):
        return self.name

    
class UserRole(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_roles')
    role=models.ForeignKey('Role',on_delete=models.CASCADE)
    
    class Meta:
        unique_together=('user','role')


class Donation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('picked', 'Picked by Volunteer'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    donor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='donations'
    )
    item_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True, null=True)
    pickup_address = models.TextField()
    contact_number = models.CharField(max_length=15)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    volunteer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='volunteer_donations'
    )
    area = models.ForeignKey(
        'Area', on_delete=models.SET_NULL, null=True, blank=True, related_name='donations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.item_name} ({self.status})"