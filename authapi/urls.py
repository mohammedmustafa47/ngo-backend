from rest_framework_nested import routers
from django.conf import settings #new
from django.conf.urls.static import static
from . import views
from django.urls import include,re_path,path
from .views import RegisterView,LoginView,DashboardView,AllUserViewSet,DonationViewSet


router = routers.DefaultRouter()
router.register('user-role',views.UserRoleViewSet,basename='user-role'),
router.register('add-role',views.UserViewSet,basename='add-role'),
router.register('users', views.AllUserViewSet, basename='users'),
router.register('donations', DonationViewSet, basename='donations')

urlpatterns = [
    path('',include(router.urls)),
    path('auth_register',RegisterView.as_view(),name="auth_register"),
    path('auth_login',LoginView.as_view(),name="auth_login"),
    path('auth_dashboard',DashboardView.as_view(),name="auth_dashboard"),

]

    # path('add-role',views.RoleSerializer,basename='add-role'),
    # path('user-role',views.UserRoleSerializer,basename='user-role')