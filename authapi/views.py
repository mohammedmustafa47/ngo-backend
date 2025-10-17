from django.shortcuts import render
from rest_framework import generics,status, permissions,viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny
# from django.contrib.auth.models import User
from .models import Role,UserRole,Donation
from django.contrib.auth import get_user_model
from .serializers import RegisterSerializer, DonationSerializer,LoginSerializer,UserSerializer,UserRoleSerializer,RoleSerializer
from django.contrib.auth import authenticate
from rest_framework.viewsets import ModelViewSet,ReadOnlyModelViewSet
from .permissions import HasRole, IsAdminRole
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
# FoodDonationSerializer,,FoodDonation

# Create your views here.

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    queryset=User.objects.all()
    # permission_class=(AllowAny)
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

class LoginView(generics.GenericAPIView):
    serializer_class=LoginSerializer

    def post(self,request,*args,**kwargs):
        username=request.data.get('username')
        password=request.data.get('password')
        role=request.data.get('role')
        user=authenticate(username=username,password=password,role=role)

        if user is not None:
            refresh=RefreshToken.for_user(user)
            user_serializer=UserSerializer(user)
            return Response({
                'refresh':str(refresh),
                'access':str(refresh.access_token),
                'user':user_serializer.data,
                'result':True
            })
        else:
            
            return Response({'detail':'invalid credentials'},status=401)
        
class DashboardView(APIView):
    permission_classes=(IsAuthenticated)
    # required_role='donor',HasRole
    def get(self,request):
        user=request.user
        user_serializer=UserSerializer(user)
        return Response({
            'message':'welcome to dashboard',
            'user':user_serializer.data
        }, 200)
    
class UserViewSet(ModelViewSet):
    queryset=Role.objects.all()
    serializer_class=RoleSerializer
    

class UserRoleViewSet(ModelViewSet):
    queryset=UserRole.objects.all()
    serializer_class=UserRoleSerializer

class AllUserViewSet(ModelViewSet):
    queryset=User.objects.all()
    serializer_class=UserSerializer
    # Use custom permission that checks the project's `role`/`UserRole` setup
    permission_classes = [IsAdminRole]

class DonationViewSet(viewsets.ModelViewSet):
    queryset = Donation.objects.all().order_by('-created_at')
    serializer_class = DonationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status']  # <-- enable status filtering

    def get_permissions(self):
        if self.action in ['create']:
            return [permissions.IsAuthenticated()]
        elif self.action in ['pick_donation', 'update_status']:
            return [permissions.IsAuthenticated()]
        else:
            return [permissions.AllowAny()]

    def perform_create(self, serializer):
        serializer.save(donor=self.request.user)

    def get_queryset(self):
        user = self.request.user
        if user.is_anonymous:
            return Donation.objects.none()

        if user.role == 'donor':
            return Donation.objects.filter(donor=user)
        elif user.role == 'volunteer':
            return Donation.objects.filter(status='pending') | Donation.objects.filter(volunteer=user)
        elif user.role == 'admin':
            return Donation.objects.all()
        return Donation.objects.none()

    @action(detail=True, methods=['post'])
    def pick_donation(self, request, pk=None):
        """Volunteer picks a pending donation"""
        donation = self.get_object()

        if donation.status != 'pending':
            return Response({'error': 'This donation is already picked.'}, status=status.HTTP_400_BAD_REQUEST)

        donation.volunteer = request.user
        donation.status = 'picked'
        donation.save()
        return Response({'message': 'Donation successfully picked!'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Volunteer updates delivery status"""
        donation = self.get_object()
        new_status = request.data.get('status')

        if donation.volunteer != request.user:
            return Response({'error': 'You are not assigned to this donation.'}, status=status.HTTP_403_FORBIDDEN)

        if new_status not in ['delivered', 'cancelled']:
            return Response({'error': 'Invalid status update.'}, status=status.HTTP_400_BAD_REQUEST)

        donation.status = new_status
        donation.save()
        return Response({'message': f'Status updated to {new_status}'}, status=status.HTTP_200_OK)