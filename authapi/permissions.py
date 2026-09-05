from rest_framework.permissions import BasePermission


class HasRole(BasePermission):
    def has_permission(self, request, view):
        required_role = getattr(view, 'required_role', None)
        if required_role:
            # deny anonymous users immediately
            if request.user is None or request.user.is_anonymous:
                return False
            # return a boolean
            return request.user.user_roles.filter(role__name__iexact=required_role).exists()
        return False


class IsAdminRole(BasePermission):
    """Allow access only to users with the 'admin' role.

    This supports both the simple `role` field on the custom User model
    and the `UserRole` relation (preferred in some serializers).
    """
    def has_permission(self, request, view):
        user = request.user
        if user is None or user.is_anonymous:
            return False

        # Check direct `role` field on the User model (if used)
        user_role_field = getattr(user, 'role', None)
        if user_role_field and str(user_role_field).lower() == 'admin':
            return True

        # Check UserRole relationship
        return user.user_roles.filter(role__name__iexact='admin').exists()


class IsOwnerOrAdmin(BasePermission):
    """Object-level permission: only the donation's donor, its Area Admin,
    or the Super Admin may update/delete it directly."""

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user is None or user.is_anonymous:
            return False

        if str(getattr(user, 'role', '')).lower() in ('admin', 'super_admin'):
            return True

        return obj.donor_id == user.id


class IsSuperAdmin(BasePermission):
    """Allow access only to the platform-wide Super Admin."""

    def has_permission(self, request, view):
        user = request.user
        if user is None or user.is_anonymous:
            return False
        return str(getattr(user, 'role', '')).lower() == 'super_admin'


class IsAreaOrSuperAdmin(BasePermission):
    """Allow access to an Area Admin (scoped to their own area, enforced via
    get_queryset) or the Super Admin (unscoped)."""

    def has_permission(self, request, view):
        user = request.user
        if user is None or user.is_anonymous:
            return False
        return str(getattr(user, 'role', '')).lower() in ('admin', 'super_admin')