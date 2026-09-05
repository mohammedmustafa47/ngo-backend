from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework import status

from .models import OTP, Role, UserRole, Donation, Area
from django.contrib.auth import get_user_model

User = get_user_model()


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AuthFlowTests(APITestCase):
    def register(self, username='donor1', email='donor1@gmail.com', password='StrongPass123!', pincode='581342'):
        return self.client.post('/authapi/auth_register', {
            'username': username, 'email': email, 'password': password, 'pincode': pincode,
        }, format='json')

    def test_register_rejects_non_gmail_email(self):
        response = self.client.post('/authapi/auth_register', {
            'username': 'baduser', 'email': 'baduser@yahoo.com', 'password': 'StrongPass123!', 'pincode': '581342',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_requires_pincode(self):
        response = self.client.post('/authapi/auth_register', {
            'username': 'nopincode', 'email': 'nopincode@gmail.com', 'password': 'StrongPass123!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_rejects_super_admin_role(self):
        response = self.client.post('/authapi/auth_register', {
            'username': 'wannabe', 'email': 'wannabe@gmail.com', 'password': 'StrongPass123!',
            'pincode': '581342', 'role': 'super_admin',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_with_unmatched_pincode_is_pending_area(self):
        self.register(pincode='000000')
        user = User.objects.get(username='donor1')
        self.assertIsNone(user.area)

    def test_register_with_matched_pincode_resolves_area(self):
        area = Area.objects.create(name='Murudeshwar', pincodes=['581342'])
        self.register(pincode='581342')
        user = User.objects.get(username='donor1')
        self.assertEqual(user.area_id, area.id)

    def test_login_blocked_until_email_verified(self):
        self.register()
        response = self.client.post('/authapi/auth_login', {
            'username': 'donor1', 'password': 'StrongPass123!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_full_register_verify_login_flow(self):
        self.register()
        otp = OTP.objects.filter(email='donor1@gmail.com', purpose='verify_email').latest('created_at')

        verify_response = self.client.post('/authapi/auth_verify_email', {
            'email': 'donor1@gmail.com', 'otp': otp.code,
        }, format='json')
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)

        login_response = self.client.post('/authapi/auth_login', {
            'username': 'donor1', 'password': 'StrongPass123!',
        }, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', login_response.data)

    def test_resend_otp_invalidates_previous_code(self):
        self.register()
        old_otp = OTP.objects.filter(email='donor1@gmail.com', purpose='verify_email').latest('created_at')

        resend_response = self.client.post('/authapi/auth_resend_otp', {
            'email': 'donor1@gmail.com',
        }, format='json')
        self.assertEqual(resend_response.status_code, status.HTTP_200_OK)

        old_otp.refresh_from_db()
        self.assertTrue(old_otp.is_used)

        stale_verify = self.client.post('/authapi/auth_verify_email', {
            'email': 'donor1@gmail.com', 'otp': old_otp.code,
        }, format='json')
        self.assertEqual(stale_verify.status_code, status.HTTP_400_BAD_REQUEST)

        new_otp = OTP.objects.filter(email='donor1@gmail.com', purpose='verify_email', is_used=False).latest('created_at')
        fresh_verify = self.client.post('/authapi/auth_verify_email', {
            'email': 'donor1@gmail.com', 'otp': new_otp.code,
        }, format='json')
        self.assertEqual(fresh_verify.status_code, status.HTTP_200_OK)

    def test_password_reset_full_flow(self):
        self.register()
        verify_otp = OTP.objects.filter(email='donor1@gmail.com', purpose='verify_email').latest('created_at')
        self.client.post('/authapi/auth_verify_email', {'email': 'donor1@gmail.com', 'otp': verify_otp.code}, format='json')

        request_response = self.client.post('/authapi/auth_password_reset/request', {
            'email': 'donor1@gmail.com',
        }, format='json')
        self.assertEqual(request_response.status_code, status.HTTP_200_OK)

        reset_otp = OTP.objects.filter(email='donor1@gmail.com', purpose='reset_password').latest('created_at')

        verify_response = self.client.post('/authapi/auth_password_reset/verify-otp', {
            'email': 'donor1@gmail.com', 'otp': reset_otp.code,
        }, format='json')
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)

        confirm_response = self.client.post('/authapi/auth_password_reset/confirm', {
            'email': 'donor1@gmail.com', 'otp': reset_otp.code,
            'new_password': 'NewStrongPass456!', 'confirm_password': 'NewStrongPass456!',
        }, format='json')
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)

        login_response = self.client.post('/authapi/auth_login', {
            'username': 'donor1', 'password': 'NewStrongPass456!',
        }, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def test_password_reset_confirm_requires_verified_otp(self):
        self.register()
        verify_otp = OTP.objects.filter(email='donor1@gmail.com', purpose='verify_email').latest('created_at')
        self.client.post('/authapi/auth_verify_email', {'email': 'donor1@gmail.com', 'otp': verify_otp.code}, format='json')

        self.client.post('/authapi/auth_password_reset/request', {'email': 'donor1@gmail.com'}, format='json')
        reset_otp = OTP.objects.filter(email='donor1@gmail.com', purpose='reset_password').latest('created_at')

        confirm_response = self.client.post('/authapi/auth_password_reset/confirm', {
            'email': 'donor1@gmail.com', 'otp': reset_otp.code,
            'new_password': 'NewStrongPass456!', 'confirm_password': 'NewStrongPass456!',
        }, format='json')
        self.assertEqual(confirm_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_profile_requires_authentication(self):
        response = self.client.get('/authapi/auth_profile')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class DonationLifecycleTests(APITestCase):
    def make_verified_user(self, username, email, role='donor'):
        user = User.objects.create_user(username=username, email=email, password='StrongPass123!')
        user.is_active = True
        user.is_email_verified = True
        user.role = role
        user.save()
        return user

    def setUp(self):
        self.donor = self.make_verified_user('donor2', 'donor2@gmail.com', role='donor')
        self.volunteer = self.make_verified_user('vol2', 'vol2@gmail.com', role='volunteer')
        self.other_volunteer = self.make_verified_user('vol3', 'vol3@gmail.com', role='volunteer')
        self.admin = self.make_verified_user('admin2', 'admin2@gmail.com', role='admin')

    def login(self, username, password='StrongPass123!'):
        response = self.client.post('/authapi/auth_login', {'username': username, 'password': password}, format='json')
        return response.data['access']

    def auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def create_donation(self):
        self.auth(self.login('donor2'))
        response = self.client.post('/authapi/donations/', {
            'item_name': 'Rice', 'quantity': 5, 'pickup_address': '123 St', 'contact_number': '1234567890',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data['id']

    def test_donor_can_create_and_only_sees_own_donations(self):
        donation_id = self.create_donation()

        other_donor = self.make_verified_user('donor3', 'donor3@gmail.com', role='donor')
        self.auth(self.login('donor3'))
        list_response = self.client.get('/authapi/donations/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        ids = [d['id'] for d in list_response.data['results']]
        self.assertNotIn(donation_id, ids)

    def test_volunteer_can_pick_pending_donation_once(self):
        donation_id = self.create_donation()

        self.auth(self.login('vol2'))
        pick_response = self.client.post(f'/authapi/donations/{donation_id}/pick_donation/')
        self.assertEqual(pick_response.status_code, status.HTTP_200_OK)

        # Once picked, the donation drops out of other volunteers' queryset
        # (get_queryset only shows a volunteer 'pending' + their own picks),
        # so a second volunteer gets a 404 rather than a 400.
        self.auth(self.login('vol3'))
        second_pick = self.client.post(f'/authapi/donations/{donation_id}/pick_donation/')
        self.assertEqual(second_pick.status_code, status.HTTP_404_NOT_FOUND)

    def test_only_assigned_volunteer_can_update_status(self):
        donation_id = self.create_donation()

        self.auth(self.login('vol2'))
        self.client.post(f'/authapi/donations/{donation_id}/pick_donation/')

        # Same visibility rule as above: vol3 can no longer see a donation
        # already picked by vol2, so this 404s rather than 403s.
        self.auth(self.login('vol3'))
        wrong_volunteer_update = self.client.post(f'/authapi/donations/{donation_id}/update_status/', {'status': 'delivered'})
        self.assertEqual(wrong_volunteer_update.status_code, status.HTTP_404_NOT_FOUND)

        self.auth(self.login('vol2'))
        correct_update = self.client.post(f'/authapi/donations/{donation_id}/update_status/', {'status': 'delivered'})
        self.assertEqual(correct_update.status_code, status.HTTP_200_OK)

    def test_non_owner_cannot_directly_update_or_delete_donation(self):
        donation_id = self.create_donation()

        self.auth(self.login('vol2'))
        update_response = self.client.patch(f'/authapi/donations/{donation_id}/', {'item_name': 'Hacked'}, format='json')
        self.assertIn(update_response.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))

    def test_owner_can_update_own_donation(self):
        donation_id = self.create_donation()

        self.auth(self.login('donor2'))
        update_response = self.client.patch(f'/authapi/donations/{donation_id}/', {'item_name': 'Wheat'}, format='json')
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)

    def test_donations_list_requires_authentication(self):
        response = self.client.get('/authapi/donations/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AreaHierarchyTests(APITestCase):
    def make_user(self, username, email, role='donor', area=None):
        user = User.objects.create_user(username=username, email=email, password='StrongPass123!')
        user.is_active = True
        user.is_email_verified = True
        user.role = role
        user.area = area
        user.save()
        return user

    def setUp(self):
        self.area_a = Area.objects.create(name='Murudeshwar', pincodes=['581342'])
        self.area_b = Area.objects.create(name='NextTown', pincodes=['581999'])

        self.super_admin = self.make_user('super1', 'super1@gmail.com', role='super_admin')
        self.admin_a = self.make_user('admina', 'admina@gmail.com', role='admin', area=self.area_a)
        self.admin_b = self.make_user('adminb', 'adminb@gmail.com', role='admin', area=self.area_b)
        self.donor_a = self.make_user('donora', 'donora@gmail.com', role='donor', area=self.area_a)
        self.volunteer_a = self.make_user('vola', 'vola@gmail.com', role='volunteer', area=self.area_a)
        self.volunteer_b = self.make_user('volb', 'volb@gmail.com', role='volunteer', area=self.area_b)

    def login(self, username, password='StrongPass123!'):
        response = self.client.post('/authapi/auth_login', {'username': username, 'password': password}, format='json')
        return response.data['access']

    def auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def create_donation_as(self, username):
        self.auth(self.login(username))
        response = self.client.post('/authapi/donations/', {
            'item_name': 'Rice', 'quantity': 5, 'pickup_address': '123 St', 'contact_number': '1234567890',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data['id']

    def test_donation_inherits_donor_area(self):
        donation_id = self.create_donation_as('donora')
        donation = Donation.objects.get(id=donation_id)
        self.assertEqual(donation.area_id, self.area_a.id)

    def test_volunteer_only_sees_pending_donations_in_own_area(self):
        donation_id = self.create_donation_as('donora')

        self.auth(self.login('volb'))
        list_response = self.client.get('/authapi/donations/')
        ids = [d['id'] for d in list_response.data['results']]
        self.assertNotIn(donation_id, ids, 'volunteer in a different area should not see this pending donation')

        self.auth(self.login('vola'))
        list_response = self.client.get('/authapi/donations/')
        ids = [d['id'] for d in list_response.data['results']]
        self.assertIn(donation_id, ids)

    def test_area_admin_only_sees_own_area_donations(self):
        donation_id = self.create_donation_as('donora')

        self.auth(self.login('adminb'))
        list_response = self.client.get('/authapi/donations/')
        ids = [d['id'] for d in list_response.data['results']]
        self.assertNotIn(donation_id, ids)

        self.auth(self.login('admina'))
        list_response = self.client.get('/authapi/donations/')
        ids = [d['id'] for d in list_response.data['results']]
        self.assertIn(donation_id, ids)

    def test_super_admin_sees_all_areas_donations(self):
        donation_id = self.create_donation_as('donora')

        self.auth(self.login('super1'))
        list_response = self.client.get('/authapi/donations/')
        ids = [d['id'] for d in list_response.data['results']]
        self.assertIn(donation_id, ids)

    def test_area_admin_only_sees_own_area_users(self):
        self.auth(self.login('admina'))
        response = self.client.get('/authapi/users/')
        usernames = [u['username'] for u in response.data['results']]
        self.assertIn('donora', usernames)
        self.assertNotIn('adminb', usernames)

    def test_super_admin_sees_all_users(self):
        self.auth(self.login('super1'))
        response = self.client.get('/authapi/users/')
        usernames = [u['username'] for u in response.data['results']]
        self.assertIn('donora', usernames)
        self.assertIn('adminb', usernames)

    def test_non_admin_cannot_access_users_list(self):
        self.auth(self.login('donora'))
        response = self.client.get('/authapi/users/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_only_super_admin_can_create_area(self):
        self.auth(self.login('admina'))
        response = self.client.post('/authapi/areas/', {'name': 'ThirdTown', 'pincodes': ['582000']}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.auth(self.login('super1'))
        response = self.client.post('/authapi/areas/', {'name': 'ThirdTown', 'pincodes': ['582000']}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_pending_area_signup_appears_in_super_admin_queue(self):
        response = self.client.post('/authapi/auth_register', {
            'username': 'pendingdonor', 'email': 'pendingdonor@gmail.com',
            'password': 'StrongPass123!', 'pincode': '000000',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.auth(self.login('super1'))
        queue_response = self.client.get('/authapi/pending-area-users')
        usernames = [u['username'] for u in queue_response.data['results']]
        self.assertIn('pendingdonor', usernames)

    def test_super_admin_can_assign_pending_user_to_area(self):
        self.client.post('/authapi/auth_register', {
            'username': 'pendingdonor2', 'email': 'pendingdonor2@gmail.com',
            'password': 'StrongPass123!', 'pincode': '000000',
        }, format='json')
        pending_user = User.objects.get(username='pendingdonor2')

        self.auth(self.login('super1'))
        response = self.client.post('/authapi/assign-area', {
            'user_id': pending_user.id, 'area_id': self.area_a.id,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        pending_user.refresh_from_db()
        self.assertEqual(pending_user.area_id, self.area_a.id)

    def test_second_area_admin_signup_for_same_area_is_rejected(self):
        response = self.client.post('/authapi/auth_register', {
            'username': 'seconadmin', 'email': 'secondadmin@gmail.com', 'password': 'StrongPass123!',
            'pincode': '581342', 'role': 'admin',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_area_admin_signup_without_matching_area_is_rejected(self):
        response = self.client.post('/authapi/auth_register', {
            'username': 'nowhereadmin', 'email': 'nowhereadmin@gmail.com', 'password': 'StrongPass123!',
            'pincode': '000000', 'role': 'admin',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AnalyticsTests(APITestCase):
    def make_user(self, username, email, role='donor', area=None):
        user = User.objects.create_user(username=username, email=email, password='StrongPass123!')
        user.is_active = True
        user.is_email_verified = True
        user.role = role
        user.area = area
        user.save()
        return user

    def setUp(self):
        self.area_a = Area.objects.create(name='Murudeshwar', pincodes=['581342'])
        self.area_b = Area.objects.create(name='NextTown', pincodes=['581999'])

        self.super_admin = self.make_user('super_a', 'super_a@gmail.com', role='super_admin')
        self.admin_a = self.make_user('admin_a', 'admin_a@gmail.com', role='admin', area=self.area_a)
        self.donor_a = self.make_user('donor_a', 'donor_a@gmail.com', role='donor', area=self.area_a)
        self.volunteer_a = self.make_user('vol_a', 'vol_a@gmail.com', role='volunteer', area=self.area_a)
        self.donor_b = self.make_user('donor_b', 'donor_b@gmail.com', role='donor', area=self.area_b)

        Donation.objects.create(
            donor=self.donor_a, item_name='Rice', pickup_address='x', contact_number='1',
            status='pending', area=self.area_a,
        )
        Donation.objects.create(
            donor=self.donor_a, item_name='Wheat', pickup_address='x', contact_number='1',
            status='delivered', area=self.area_a, volunteer=self.volunteer_a,
        )
        Donation.objects.create(
            donor=self.donor_b, item_name='Milk', pickup_address='x', contact_number='1',
            status='pending', area=self.area_b,
        )

    def login(self, username, password='StrongPass123!'):
        response = self.client.post('/authapi/auth_login', {'username': username, 'password': password}, format='json')
        return response.data['access']

    def auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_super_admin_analytics_totals_and_by_area(self):
        self.auth(self.login('super_a'))
        response = self.client.get('/authapi/analytics/super-admin')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['totals']['pending'], 2)
        self.assertEqual(response.data['totals']['delivered'], 1)
        area_names = [a['area'] for a in response.data['by_area']]
        self.assertIn('Murudeshwar', area_names)
        self.assertIn('NextTown', area_names)

    def test_non_super_admin_cannot_access_super_admin_analytics(self):
        self.auth(self.login('admin_a'))
        response = self.client.get('/authapi/analytics/super-admin')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_area_admin_analytics_scoped_to_own_area(self):
        self.auth(self.login('admin_a'))
        response = self.client.get('/authapi/analytics/area-admin')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['area'], 'Murudeshwar')
        self.assertEqual(response.data['totals']['pending'], 1)
        self.assertEqual(response.data['totals']['delivered'], 1)

    def test_super_admin_can_drill_into_specific_area(self):
        self.auth(self.login('super_a'))
        response = self.client.get(f'/authapi/analytics/area-admin?area_id={self.area_b.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['area'], 'NextTown')
        self.assertEqual(response.data['totals']['pending'], 1)

    def test_super_admin_area_admin_analytics_requires_area_id(self):
        self.auth(self.login('super_a'))
        response = self.client.get('/authapi/analytics/area-admin')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_donor_analytics_scoped_to_own_donations(self):
        self.auth(self.login('donor_a'))
        response = self.client.get('/authapi/analytics/donor')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['totals']['pending'], 1)
        self.assertEqual(response.data['totals']['delivered'], 1)

    def test_volunteer_analytics_scoped_to_own_deliveries(self):
        self.auth(self.login('vol_a'))
        response = self.client.get('/authapi/analytics/volunteer')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['totals']['delivered'], 1)

    def test_analytics_requires_authentication(self):
        response = self.client.get('/authapi/analytics/donor')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
