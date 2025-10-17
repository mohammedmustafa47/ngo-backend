from rest_framework import serializers
# from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from .models import Role,UserRole,Donation
# ,FoodDonation

User = get_user_model()

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

        return user
    
class LoginSerializer(serializers.Serializer):
    username=serializers.CharField(required=True)
    password=serializers.CharField(required=True, write_only=True)

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