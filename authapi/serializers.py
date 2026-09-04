import re
from rest_framework import serializers
# from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import Role,UserRole,Donation,OTP
from .utils import create_otp, send_otp_email
# ,FoodDonation

User = get_user_model()

GMAIL_REGEX = re.compile(r'^[A-Za-z0-9_.+-]+@gmail\.com$')

class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    class Meta:
        model=User
        fields=('id','username','email', 'role')
        
    def get_role(self, obj):
        """Get role from UserRole relationship"""
        try:
            # First try to get from UserRole relationship
            user_role = UserRole.objects.get(user=obj)
            return user_role.role.name
        except UserRole.DoesNotExist:
            # Fallback to direct role field on User model
            return getattr(obj, 'role', None)
        # try:
        #     user_role = UserRole.objects.get(user=obj)
        #     return user_role.role.name  # Assuming Role model has a 'name' field
        # except UserRole.DoesNotExist:
        #     return None
        # , 'role'

class RegisterSerializer(serializers.ModelSerializer):
    role=serializers.CharField(write_only=True,required=False)
    class Meta:
        model=User
        fields=('username','email','password','role')

    def validate_email(self, value):
        if not GMAIL_REGEX.match(value):
            raise serializers.ValidationError(
                "Email must be a valid gmail address in the form example@gmail.com"
            )
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, data):
            """Custom validation at serializer level"""
            role_name = data.get('role')

            if role_name and role_name.lower() == "admin":
                if UserRole.objects.filter(role__name__iexact="admin").exists():
                    raise serializers.ValidationError("Only one Admin account is allowed.")

            return data

    def create(self,validated_data):
        role_name=validated_data.pop('role',None)
        user=User.objects.create_user(
            validated_data['username'],
            validated_data['email'],
            validated_data['password'],
        )
        user.is_active = False
        user.is_email_verified = False
        user.save()
        # If a role was provided, try to resolve it and attach it to the user
        if role_name:
            try:
                role_obj = Role.objects.get(name__iexact=role_name)
            except Role.DoesNotExist:
                # If the role is invalid, remove the created user to avoid
                # leaving a partially-created account, then raise a validation
                # error back to the client.
                user.delete()
                raise serializers.ValidationError({"role": f"Role '{role_name}' does not exist."})

            # create the relationship and keep the simple `role` field in
            # sync for compatibility with existing code that reads it
            UserRole.objects.create(user=user, role=role_obj)
            # keep the string field on the user in sync
            try:
                user.role = str(role_obj.name).lower()
                user.save()
            except Exception:
                # if saving the user fails for any unexpected reason, clean up
                user.delete()
                raise serializers.ValidationError({"role": "Unable to assign role to user."})

        otp = create_otp(user.email, 'verify_email')
        send_otp_email(user.email, otp.code, 'verify_email')

        return user

class ProfileSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'is_email_verified', 'date_joined', 'last_login',
        )
        read_only_fields = fields

    def get_role(self, obj):
        try:
            return UserRole.objects.get(user=obj).role.name
        except UserRole.DoesNotExist:
            return getattr(obj, 'role', None)


class LoginSerializer(serializers.Serializer):
    username=serializers.CharField(required=True)
    password=serializers.CharField(required=True, write_only=True)


class VerifyEmailSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, max_length=4, min_length=4)

    def validate(self, data):
        try:
            user = User.objects.get(email__iexact=data['email'])
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "No user found with this email."})

        if user.is_email_verified:
            raise serializers.ValidationError({"email": "Email is already verified."})

        otp = OTP.objects.filter(
            email__iexact=data['email'], purpose='verify_email', is_used=False
        ).order_by('-created_at').first()

        if not otp or otp.code != data['otp']:
            raise serializers.ValidationError({"otp": "Invalid OTP."})

        if otp.is_expired():
            raise serializers.ValidationError({"otp": "OTP has expired."})

        data['user'] = user
        data['otp_obj'] = otp
        return data


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        try:
            user = User.objects.get(email__iexact=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("No user found with this email.")

        if user.is_email_verified:
            raise serializers.ValidationError("Email is already verified.")

        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        if not User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("No user found with this email.")
        return value


class PasswordResetVerifySerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, max_length=4, min_length=4)

    def validate(self, data):
        otp = OTP.objects.filter(
            email__iexact=data['email'], purpose='reset_password', is_used=False
        ).order_by('-created_at').first()

        if not otp or otp.code != data['otp']:
            raise serializers.ValidationError({"otp": "Invalid OTP."})

        if otp.is_expired():
            raise serializers.ValidationError({"otp": "OTP has expired."})

        data['otp_obj'] = otp
        return data


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, max_length=4, min_length=4)
    new_password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        try:
            user = User.objects.get(email__iexact=data['email'])
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "No user found with this email."})

        otp = OTP.objects.filter(
            email__iexact=data['email'], purpose='reset_password', is_used=False, is_verified=True
        ).order_by('-created_at').first()

        if not otp or otp.code != data['otp']:
            raise serializers.ValidationError({"otp": "OTP not verified. Please verify the OTP first."})

        if otp.is_expired():
            raise serializers.ValidationError({"otp": "OTP has expired."})

        validate_password(data['new_password'], user=user)

        data['user'] = user
        data['otp_obj'] = otp
        return data

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model=Role
        fields='__all__'

class UserRoleSerializer(serializers.ModelSerializer):
    user=serializers.CharField(required=False,allow_null=True)
    role=serializers.CharField(required=False,allow_null=True)
    class Meta:
        model=UserRole
        fields='__all__'
        read_only_fields = ('id',)

    def create(self,validated_data):
        user_name=validated_data.pop('user',None)
        role_name=validated_data.pop('role',None)

        user=None
        if user_name:
            try:
                user=User.objects.get(username=user_name)
            except User.DoesNotExist:
                raise serializers.ValidationError(f'user with name {user_name} does not exist.')

        role=None
        if role_name:
            try:
                role=Role.objects.get(name=role_name)
            except Role.DoesNotExist:
                raise serializers.ValidationError(f'role with {role_name} does not exist')
            
        userrole=UserRole.objects.create(user=user,role=role,**validated_data)

        return userrole
    
class DonationSerializer(serializers.ModelSerializer):
    donor_name = serializers.CharField(source='donor.username', read_only=True)
    volunteer_name = serializers.CharField(source='volunteer.username', read_only=True)

    class Meta:
        model = Donation
        fields = '__all__'
        read_only_fields = ['donor', 'status', 'volunteer', 'created_at']