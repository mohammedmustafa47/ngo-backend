from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Donation, Area
from .permissions import IsSuperAdmin, IsAreaOrSuperAdmin
from django.contrib.auth import get_user_model

User = get_user_model()

STATUSES = ['pending', 'picked', 'delivered', 'cancelled']


def build_totals(queryset):
    totals = {s: 0 for s in STATUSES}
    for row in queryset.values('status').annotate(count=Count('id')):
        totals[row['status']] = row['count']
    return totals


def build_timeseries(queryset, date_field='created_at'):
    rows = (
        queryset
        .annotate(day=TruncDate(date_field))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    return [{'date': row['day'].isoformat(), 'count': row['count']} for row in rows if row['day']]


def build_leaderboard(queryset, limit=5):
    rows = (
        queryset.filter(status='delivered', volunteer__isnull=False)
        .values('volunteer__username')
        .annotate(delivered=Count('id'))
        .order_by('-delivered')[:limit]
    )
    return [{'username': row['volunteer__username'], 'delivered': row['delivered']} for row in rows]


def build_avg_delivery_hours(queryset):
    rows = queryset.filter(status='delivered', updated_at__isnull=False).values_list('created_at', 'updated_at')
    diffs = [(updated - created).total_seconds() for created, updated in rows if created and updated]
    if not diffs:
        return None
    return round((sum(diffs) / len(diffs)) / 3600, 2)


def build_users_by_role(queryset):
    return {row['role']: row['count'] for row in queryset.values('role').annotate(count=Count('id'))}


def build_by_area():
    rows = (
        Donation.objects.values('area__name')
        .annotate(
            pending=Count('id', filter=Q(status='pending')),
            picked=Count('id', filter=Q(status='picked')),
            delivered=Count('id', filter=Q(status='delivered')),
            cancelled=Count('id', filter=Q(status='cancelled')),
        )
        .order_by('area__name')
    )
    result = []
    for row in rows:
        total = row['pending'] + row['picked'] + row['delivered'] + row['cancelled']
        result.append({
            'area': row['area__name'] or 'Unassigned',
            'pending': row['pending'],
            'picked': row['picked'],
            'delivered': row['delivered'],
            'cancelled': row['cancelled'],
            'total': total,
        })
    return result


class SuperAdminAnalyticsView(APIView):
    """Cross-area rollup for the Super Admin dashboard."""
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        donations = Donation.objects.all()
        return Response({
            'totals': build_totals(donations),
            'timeseries': build_timeseries(donations),
            'leaderboard': build_leaderboard(donations),
            'by_area': build_by_area(),
            'users_by_role': build_users_by_role(User.objects.all()),
            'avg_delivery_hours': build_avg_delivery_hours(donations),
        })


class AreaAdminAnalyticsView(APIView):
    """Single-area dashboard. An Area Admin sees their own area; a Super
    Admin can drill into any area via ?area_id=."""
    permission_classes = [IsAreaOrSuperAdmin]

    def get(self, request):
        user = request.user

        if user.role == 'super_admin':
            area_id = request.query_params.get('area_id')
            if not area_id:
                return Response(
                    {'detail': 'area_id query param is required for Super Admin drill-down.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            area = get_object_or_404(Area, id=area_id)
        else:
            area = user.area
            if area is None:
                return Response(
                    {'detail': 'You are not assigned to an area yet.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        donations = Donation.objects.filter(area=area)
        return Response({
            'area': area.name,
            'totals': build_totals(donations),
            'timeseries': build_timeseries(donations),
            'leaderboard': build_leaderboard(donations),
            'users_by_role': build_users_by_role(User.objects.filter(area=area)),
            'avg_delivery_hours': build_avg_delivery_hours(donations),
        })


class DonorAnalyticsView(APIView):
    """A donor's own contribution stats."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        donations = Donation.objects.filter(donor=request.user)
        return Response({
            'totals': build_totals(donations),
            'timeseries': build_timeseries(donations),
            'total_items_donated': donations.aggregate(total=Sum('quantity'))['total'] or 0,
        })


class VolunteerAnalyticsView(APIView):
    """A volunteer's own pickup/delivery stats."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        donations = Donation.objects.filter(volunteer=request.user)
        return Response({
            'totals': build_totals(donations),
            'timeseries': build_timeseries(donations.filter(status='delivered')),
            'avg_delivery_hours': build_avg_delivery_hours(donations),
        })
