from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.


class User(AbstractUser):
    # Define role choices
    ROLES = (
        ('admin', 'Admin'),
        ('donor', 'Donor'),
        ('volunteer', 'Volunteer'),
    )

    # Add role field with choices
    role = models.CharField(max_length=10, choices=ROLES,default= 'donor')

    # def __str__(self):
    #     return self.username


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
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.item_name} ({self.status})"