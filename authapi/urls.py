from rest_framework_nested import routers
from django.conf import settings #new
from django.conf.urls.static import static

from authapi import views
from django.urls import include,re_path,path
from .views import (
    RegisterView,LoginView,DashboardView,AllUserViewSet,DonationViewSet,
    VerifyEmailView, PasswordResetRequestView, PasswordResetVerifyView,
    PasswordResetConfirmView, ProfileView, ResendOTPView, AreaViewSet,
    PendingAreaUsersView, UnattendedDonationsView, AssignAreaView, CreateAreaAdminView,
)
from .analytics import (
    SuperAdminAnalyticsView, AreaAdminAnalyticsView, DonorAnalyticsView, VolunteerAnalyticsView,
)


router = routers.DefaultRouter()
router.register('user-role',views.UserRoleViewSet,basename='user-role'),
router.register('add-role',views.UserViewSet,basename='add-role'),
router.register('users', views.AllUserViewSet, basename='users'),
router.register('donations', DonationViewSet, basename='donations')
router.register('areas', AreaViewSet, basename='areas')

urlpatterns = [
    path('',include(router.urls)),
    path('auth_register',RegisterView.as_view(),name="auth_register"),
    path('auth_verify_email',VerifyEmailView.as_view(),name="auth_verify_email"),
    path('auth_resend_otp',ResendOTPView.as_view(),name="auth_resend_otp"),
    path('auth_login',LoginView.as_view(),name="auth_login"),
    path('auth_dashboard',DashboardView.as_view(),name="auth_dashboard"),
    path('auth_profile',ProfileView.as_view(),name="auth_profile"),
    path('auth_password_reset/request',PasswordResetRequestView.as_view(),name="auth_password_reset_request"),
    path('auth_password_reset/verify-otp',PasswordResetVerifyView.as_view(),name="auth_password_reset_verify"),
    path('auth_password_reset/confirm',PasswordResetConfirmView.as_view(),name="auth_password_reset_confirm"),
    path('pending-area-users',PendingAreaUsersView.as_view(),name="pending_area_users"),
    path('unattended-donations',UnattendedDonationsView.as_view(),name="unattended_donations"),
    path('assign-area',AssignAreaView.as_view(),name="assign_area"),
    path('create-area-admin',CreateAreaAdminView.as_view(),name="create_area_admin"),
    path('analytics/super-admin',SuperAdminAnalyticsView.as_view(),name="analytics_super_admin"),
    path('analytics/area-admin',AreaAdminAnalyticsView.as_view(),name="analytics_area_admin"),
    path('analytics/donor',DonorAnalyticsView.as_view(),name="analytics_donor"),
    path('analytics/volunteer',VolunteerAnalyticsView.as_view(),name="analytics_volunteer"),

]

    # path('add-role',views.RoleSerializer,basename='add-role'),
    # path('user-role',views.UserRoleSerializer,basename='user-role')