from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Community, CommunityMembership


User = get_user_model()


class CommunityDiscoveryTests(APITestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            username='creator',
            email='creator@example.com',
            password='pass',
            phone_number='+12125550123',
            is_verified=True,
            has_completed_profile=True,
        )
        self.visitor = User.objects.create_user(
            username='visitor',
            email='visitor@example.com',
            password='pass',
            phone_number='+12125550124',
            is_verified=True,
            has_completed_profile=True,
        )
        self.third = User.objects.create_user(
            username='third',
            email='third@example.com',
            password='pass',
            phone_number='+12125550125',
            is_verified=True,
            has_completed_profile=True,
        )
        self.client.force_authenticate(self.creator)

    def create_community(
        self, name, latitude, longitude, is_private=False, city_name='New York'
    ):
        response = self.client.post(
            reverse('community-list-create'),
            {
                'name': name,
                'latitude': latitude,
                'longitude': longitude,
                'city_name': city_name,
                'country_code': 'US',
                'is_private': is_private,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return Community.objects.get(id=response.data['id'])

    def test_country_is_derived_from_verified_phone_number(self):
        response = self.client.get(reverse('community-location-context'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['country_code'], 'US')

    def test_create_requires_phone_country_and_city_coordinates(self):
        response = self.client.post(
            reverse('community-list-create'),
            {
                'name': 'New York Creators',
                'latitude': 40.7128,
                'longitude': -74.0060,
                'city_name': 'New York',
                'country_code': 'GB',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('verified phone number', str(response.data).lower())

    def test_selected_city_name_is_returned_by_list_and_detail(self):
        community = self.create_community(
            'Brooklyn Creators', 40.6782, -73.9442, city_name='Brooklyn'
        )

        listing = self.client.get(reverse('community-list-create'))
        listed = next(item for item in listing.data if item['id'] == community.id)
        detail = self.client.get(reverse('community-detail', args=[community.id]))

        self.assertEqual(listed['city_name'], 'Brooklyn')
        self.assertEqual(detail.data['city_name'], 'Brooklyn')

    def test_location_ranking_and_member_count_fallback(self):
        nearby = self.create_community(
            'Nearby', 40.7128, -74.0060
        )
        popular = self.create_community(
            'Popular', 34.0522, -118.2437
        )
        CommunityMembership.objects.create(community=popular, user=self.visitor)
        CommunityMembership.objects.create(community=popular, user=self.third)

        by_members = self.client.get(reverse('community-list-create'))
        self.assertEqual(by_members.data[0]['id'], popular.id)

        by_distance = self.client.get(
            reverse('community-list-create'),
            {'latitude': 40.7306, 'longitude': -73.9352},
        )
        self.assertEqual(by_distance.data[0]['id'], nearby.id)
        self.assertIsNotNone(by_distance.data[0]['distance_km'])

    def test_private_community_is_hidden_and_requires_invite(self):
        private = self.create_community(
            'Private Circle', 40.7128, -74.0060, is_private=True
        )
        self.client.force_authenticate(self.visitor)

        response = self.client.get(reverse('community-list-create'))
        self.assertNotIn(private.id, [item['id'] for item in response.data])

        response = self.client.post(
            reverse('community-join', args=[private.id])
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_detail_is_readable_but_management_is_creator_only(self):
        public = self.create_community(
            'Public Detail', 40.7128, -74.0060
        )
        private = self.create_community(
            'Hidden Detail', 40.7128, -74.0060, is_private=True
        )
        self.client.force_authenticate(self.visitor)

        detail = self.client.get(reverse('community-detail', args=[public.id]))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data['id'], public.id)

        hidden = self.client.get(reverse('community-detail', args=[private.id]))
        self.assertEqual(hidden.status_code, status.HTTP_404_NOT_FOUND)

        blocked_patch = self.client.patch(
            reverse('community-detail', args=[public.id]),
            {'name': 'Visitor Rename'},
            format='json',
        )
        self.assertEqual(blocked_patch.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.creator)
        patched = self.client.patch(
            reverse('community-detail', args=[public.id]),
            {'name': 'Creator Rename'},
            format='json',
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        self.assertEqual(patched.data['name'], 'Creator Rename')

    def test_private_invite_is_single_use(self):
        private = self.create_community(
            'Invite Only', 40.7128, -74.0060, is_private=True
        )
        response = self.client.post(
            reverse('community-invite-create', args=[private.id])
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        token = response.data['invite_url'].rstrip('/').rsplit('/', 1)[-1]

        self.client.force_authenticate(self.visitor)
        preview = self.client.get(reverse('community-invite', args=[token]))
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        self.assertEqual(preview.data['id'], private.id)

        joined = self.client.post(reverse('community-invite', args=[token]))
        self.assertEqual(joined.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            CommunityMembership.objects.filter(
                community=private,
                user=self.visitor,
            ).exists()
        )

        self.client.force_authenticate(self.third)
        reused = self.client.post(reverse('community-invite', args=[token]))
        self.assertEqual(reused.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            CommunityMembership.objects.filter(
                community=private,
                user=self.third,
            ).exists()
        )
