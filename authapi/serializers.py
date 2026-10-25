import re
from rest_framework import serializers
# from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import Role,UserRole,Donation,OTP,Area
from .utils import create_otp, send_otp_email, resolve_area
# ,FoodDonation

User = get_user_model()

GMAIL_REGEX = re.compile(r'^[A-Za-z0-9_.+-]+@gmail\.com$')

class AreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Area
        fields = ('id', 'name', 'pincodes', 'is_active', 'created_at')


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    area = serializers.SerializerMethodField()

    class Meta:
        model=User
        fields=('id','username','email', 'role', 'area')

    def get_area(self, obj):
        return obj.area.name if obj.area_id else None

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
    pincode=serializers.CharField(write_only=True, required=True, max_length=10)

    class Meta:
        model=User
        fields=('username','email','password','role','pincode')

    def validate_email(self, value):
        if not GMAIL_REGEX.match(value):
            raise serializers.ValidationError(
                "Email must be a valid gmail address in the form example@gmail.com"
            )
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, data):
            """Custom validation at serializer level"""
            role_name = data.get('role')

            if role_name and role_name.lower() in ('super_admin', 'admin'):
                raise serializers.ValidationError(
                    {"role": "Super Admin and Area Admin accounts cannot be created through registration. "
                              "Contact the Super Admin."}
                )

            return data

    def create(self,validated_data):
        role_name=validated_data.pop('role',None)
        pincode=validated_data.pop('pincode')
        user=User.objects.create_user(
            validated_data['username'],
            validated_data['email'],
            validated_data['password'],
        )
        user.is_active = False
        user.is_email_verified = False
        user.pincode = pincode
        user.area = resolve_area(pincode)
        user.save()

        # If a role was provided, set it directly. `validate()` above already
        # rejects admin/super_admin, so this is just donor/volunteer at this point.
        # (Not related to the separate Role/UserRole custom-badges table.)
        if role_name:
            user.role = role_name.lower()
            user.save()

        otp = create_otp(user.email, 'verify_email')
        send_otp_email(user.email, otp.code, 'verify_email')

        return user

class ProfileSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    area = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'area', 'pincode', 'is_email_verified', 'date_joined', 'last_login',
        )
        read_only_fields = fields

    def get_role(self, obj):
        try:
            return UserRole.objects.get(user=obj).role.name
        except UserRole.DoesNotExist:
            return getattr(obj, 'role', None)

    def get_area(self, obj):
        if obj.area_id:
            return obj.area.name
        if str(obj.role).lower() == 'super_admin':
            return None
        return 'pending'


class LoginSerializer(serializers.Serializer):
    email=serializers.EmailField(required=True)
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

class CreateAreaAdminSerializer(serializers.Serializer):
    """Used by the Super Admin to directly provision an Area Admin account
    for a given Area. No self-signup or OTP step — the account is created
    active and verified since the Super Admin is vouching for it."""

    username = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    area_id = serializers.IntegerField()

    def validate_email(self, value):
        if not GMAIL_REGEX.match(value):
            raise serializers.ValidationError(
                "Email must be a valid gmail address in the form example@gmail.com"
            )
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_area_id(self, value):
        try:
            area = Area.objects.get(id=value)
        except Area.DoesNotExist:
            raise serializers.ValidationError("Area not found.")

        if User.objects.filter(role='admin', area=area).exists():
            raise serializers.ValidationError("This area already has an Area Admin.")

        return value

    def create(self, validated_data):
        area = Area.objects.get(id=validated_data['area_id'])
        user = User.objects.create_user(
            validated_data['username'],
            validated_data['email'],
            validated_data['password'],
        )
        user.role = 'admin'
        user.area = area
        user.pincode = (area.pincodes or [None])[0] or ''
        user.is_active = True
        user.is_email_verified = True
        user.save()
        return user


class AssignAreaSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    area_id = serializers.IntegerField()

    def validate(self, data):
        try:
            user = User.objects.get(id=data['user_id'])
        except User.DoesNotExist:
            raise serializers.ValidationError({"user_id": "User not found."})

        try:
            area = Area.objects.get(id=data['area_id'])
        except Area.DoesNotExist:
            raise serializers.ValidationError({"area_id": "Area not found."})

        if user.role == 'admin' and User.objects.filter(role='admin', area=area).exclude(id=user.id).exists():
            raise serializers.ValidationError({"area_id": "This area already has an Area Admin."})

        data['user'] = user
        data['area'] = area
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
        read_only_fields = ['donor', 'status', 'volunteer', 'area', 'created_at']
        extra_kwargs = {'pickup_pincode': {'required': True, 'allow_blank': False}}

    def validate_pickup_pincode(self, value):
        value = value.strip()
        area = resolve_area(value)
        if not area:
            raise serializers.ValidationError("We don't operate in this pincode yet.")
        # Area is decided by the server from the pincode, never by the client.
        self._resolved_area = area
        return value

    def create(self, validated_data):
        validated_data['area'] = self._resolved_area
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'pickup_pincode' in validated_data:
            validated_data['area'] = self._resolved_area
        return super().update(instance, validated_data)