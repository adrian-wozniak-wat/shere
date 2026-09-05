from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from emotion_analyzer.models import HomeAssistantCredentials, Entity, Camera

User = get_user_model()

class ConfigurationCRUDTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client.login(username='testuser', password='password123')

    def test_add_credential(self):
        response = self.client.post(reverse('configuration_page'), {
            'action': 'add_credential',
            'username': 'ha_user_1',
            'host': '192.168.1.100',
            'port': 8123,
            'token': 'ha_token_1'
        })
        self.assertRedirects(response, '/?tab=credentials')
        self.assertEqual(HomeAssistantCredentials.objects.count(), 1)
        cred = HomeAssistantCredentials.objects.first()
        self.assertEqual(cred.username, 'ha_user_1')
        self.assertEqual(cred.host, '192.168.1.100')
        self.assertEqual(cred.port, 8123)
        self.assertEqual(cred.token, 'ha_token_1')
        self.assertEqual(cred.user, self.user)

    def test_edit_credential(self):
        cred = HomeAssistantCredentials.objects.create(
            user=self.user,
            username='ha_user_1',
            host='localhost',
            port=8123
        )
        cred.token = 'old_token'
        cred.save()

        # Update username and token
        response = self.client.post(reverse('configuration_page'), {
            'action': 'edit_credential',
            'pk': cred.id,
            'username': 'ha_user_updated',
            'host': '192.168.1.200',
            'port': 9000,
            'token': 'new_token'
        })
        self.assertRedirects(response, '/?tab=credentials')
        cred.refresh_from_db()
        self.assertEqual(cred.username, 'ha_user_updated')
        self.assertEqual(cred.host, '192.168.1.200')
        self.assertEqual(cred.port, 9000)
        self.assertEqual(cred.token, 'new_token')

        # Update without token (should keep old one)
        response = self.client.post(reverse('configuration_page'), {
            'action': 'edit_credential',
            'pk': cred.id,
            'username': 'ha_user_updated_2',
            'host': '192.168.1.200',
            'port': 9000,
            'token': ''
        })
        self.assertRedirects(response, '/?tab=credentials')
        cred.refresh_from_db()
        self.assertEqual(cred.username, 'ha_user_updated_2')
        self.assertEqual(cred.token, 'new_token')

    def test_cannot_create_multiple_credentials(self):
        # Create first credentials
        cred = HomeAssistantCredentials.objects.create(
            user=self.user,
            username='user1',
            host='host1',
            port=8123,
        )
        cred.token = 'token'
        cred.save()
        
        # Try to add second credentials via POST
        response = self.client.post(reverse('configuration_page'), {
            'action': 'add_credential',
            'username': 'user2',
            'host': 'host2',
            'port': 8124,
            'token': 'token'
        })
        
        # Should not redirect (re-renders the page with validation error)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(HomeAssistantCredentials.objects.count(), 1)
        self.assertContains(response, "Only one Home Assistant Credentials object is allowed")

    def test_delete_credential(self):
        cred = HomeAssistantCredentials.objects.create(
            user=self.user,
            username='ha_user_1',
            host='localhost',
            port=8123
        )
        cred.token = 'token'
        cred.save()
        self.assertEqual(HomeAssistantCredentials.objects.count(), 1)

        response = self.client.post(reverse('configuration_page'), {
            'action': 'delete_credential',
            'pk': cred.id
        })
        self.assertRedirects(response, '/?tab=credentials')
        self.assertEqual(HomeAssistantCredentials.objects.count(), 0)

    def test_add_entity(self):
        response = self.client.post(reverse('configuration_page'), {
            'action': 'add_entity',
            'entity_id': 'sensor.temp',
            'name': 'Living Room Temp',
            'location': 'Living Room',
            'unit_of_measurement': '°C'
        })
        self.assertRedirects(response, '/?tab=entities')
        self.assertEqual(Entity.objects.count(), 1)
        entity = Entity.objects.first()
        self.assertEqual(entity.entity_id, 'sensor.temp')
        self.assertEqual(entity.name, 'Living Room Temp')
        self.assertEqual(entity.location, 'Living Room')
        self.assertEqual(entity.unit_of_measurement, '°C')

    def test_edit_entity(self):
        entity = Entity.objects.create(
            entity_id='sensor.temp',
            name='Old Name',
            location='Living Room',
            unit_of_measurement='°C'
        )
        response = self.client.post(reverse('configuration_page'), {
            'action': 'edit_entity',
            'pk': entity.id,
            'entity_id': 'sensor.temp_updated',
            'name': 'New Name',
            'location': 'Kitchen',
            'unit_of_measurement': 'F'
        })
        self.assertRedirects(response, '/?tab=entities')
        entity.refresh_from_db()
        self.assertEqual(entity.entity_id, 'sensor.temp_updated')
        self.assertEqual(entity.name, 'New Name')
        self.assertEqual(entity.location, 'Kitchen')
        self.assertEqual(entity.unit_of_measurement, 'F')

    def test_delete_entity(self):
        entity = Entity.objects.create(
            entity_id='sensor.temp',
            location='Living Room'
        )
        self.assertEqual(Entity.objects.count(), 1)
        response = self.client.post(reverse('configuration_page'), {
            'action': 'delete_entity',
            'pk': entity.id
        })
        self.assertRedirects(response, '/?tab=entities')
        self.assertEqual(Entity.objects.count(), 0)

    def test_add_camera(self):
        response = self.client.post(reverse('configuration_page'), {
            'action': 'add_camera',
            'camera_id': 'camera.living_room',
            'name': 'Living Room Cam Name',
            'location': 'Living Room Cam'
        })
        self.assertRedirects(response, '/?tab=cameras')
        self.assertEqual(Camera.objects.count(), 1)
        camera = Camera.objects.first()
        self.assertEqual(camera.camera_id, 'camera.living_room')
        self.assertEqual(camera.name, 'Living Room Cam Name')
        self.assertEqual(camera.location, 'Living Room Cam')

    def test_edit_camera(self):
        camera = Camera.objects.create(
            camera_id='camera.living_room',
            name='Old Cam Name',
            location='Living Room Cam'
        )
        response = self.client.post(reverse('configuration_page'), {
            'action': 'edit_camera',
            'pk': camera.id,
            'camera_id': 'camera.kitchen',
            'name': 'New Cam Name',
            'location': 'Kitchen Cam'
        })
        self.assertRedirects(response, '/?tab=cameras')
        camera.refresh_from_db()
        self.assertEqual(camera.camera_id, 'camera.kitchen')
        self.assertEqual(camera.name, 'New Cam Name')
        self.assertEqual(camera.location, 'Kitchen Cam')

    def test_delete_camera(self):
        camera = Camera.objects.create(
            camera_id='camera.living_room',
            location='Living Room Cam'
        )
        self.assertEqual(Camera.objects.count(), 1)
        response = self.client.post(reverse('configuration_page'), {
            'action': 'delete_camera',
            'pk': camera.id
        })
        self.assertRedirects(response, '/?tab=cameras')
        self.assertEqual(Camera.objects.count(), 0)
