from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from emotion_analyzer.models import (
    HomeAssistantCredentials,
    Entity,
    Camera,
    PollCycle,
    CameraSnapshot,
    EntityStatus
)

User = get_user_model()

class PagesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')

    def test_configuration_page_requires_login(self):
        response = self.client.get(reverse('configuration_page'))
        self.assertEqual(response.status_code, 302)  # Should redirect to login

    def test_login_page_renders(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/login.html')

    def test_run_page_requires_login(self):
        response = self.client.get(reverse('run_page'))
        self.assertEqual(response.status_code, 302)  # Should redirect to login

    def test_configuration_page_authenticated(self):
        self.client.login(username='testuser', password='password123')
        response = self.client.get(reverse('configuration_page'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'emotion_analyzer/configuration.html')

    def test_run_page_authenticated(self):
        self.client.login(username='testuser', password='password123')
        response = self.client.get(reverse('run_page'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'emotion_analyzer/run.html')
        self.assertContains(response, 'Run Emotion Analysis')
        self.assertContains(response, 'Interval Value')
        self.assertContains(response, 'Interval Period')

    def test_results_page_requires_login(self):
        response = self.client.get(reverse('results_page'))
        self.assertEqual(response.status_code, 302)

    def test_results_page_authenticated(self):
        # Create Entity and Camera
        camera = Camera.objects.create(camera_id='camera.living_room', name='Living Room Camera', location='Living Room')
        entity = Entity.objects.create(entity_id='sensor.temp', name='Temperature Sensor', location='Living Room', unit_of_measurement='°C')
        
        # Create PollCycle, CameraSnapshot, EntityStatus
        poll_cycle = PollCycle.objects.create()
        CameraSnapshot.objects.create(
            poll_cycle=poll_cycle,
            camera=camera,
            detected_emotion='happy',
            confidence_score=0.95
        )
        EntityStatus.objects.create(
            poll_cycle=poll_cycle,
            entity=entity,
            state_value='22.5'
        )

        self.client.login(username='testuser', password='password123')
        response = self.client.get(reverse('results_page'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'emotion_analyzer/results.html')
        self.assertContains(response, 'Analysis Results')
        self.assertContains(response, 'Download CSV')
        
        # Verify headers
        self.assertContains(response, 'Living Room Camera Emotion')
        self.assertContains(response, 'Living Room Camera Confidence')
        self.assertContains(response, 'Temperature Sensor State')
        self.assertContains(response, 'Temperature Sensor Unit')

        # Verify values
        self.assertContains(response, 'happy')
        self.assertContains(response, '0.95')
        self.assertContains(response, '22.5')

    def test_results_page_pagination(self):
        # Create 55 Poll Cycles
        for _ in range(55):
            PollCycle.objects.create()

        self.client.login(username='testuser', password='password123')
        
        # Get page 1
        response = self.client.get(reverse('results_page'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('page_obj', response.context)
        page_obj = response.context['page_obj']
        self.assertEqual(len(page_obj), 50)
        self.assertTrue(page_obj.has_next())
        self.assertFalse(page_obj.has_previous())
        self.assertContains(response, 'Page 1 of 2')

        # Get page 2
        response = self.client.get(reverse('results_page') + "?page=2")
        self.assertEqual(response.status_code, 200)
        self.assertIn('page_obj', response.context)
        page_obj = response.context['page_obj']
        self.assertEqual(len(page_obj), 5)
        self.assertFalse(page_obj.has_next())
        self.assertTrue(page_obj.has_previous())
        self.assertContains(response, 'Page 2 of 2')

    def test_results_page_download_csv(self):
        # Create Entity and Camera
        camera = Camera.objects.create(camera_id='camera.living_room', name='Living Room Camera', location='Living Room')
        entity = Entity.objects.create(entity_id='sensor.temp', name='Temperature Sensor', location='Living Room', unit_of_measurement='°C')
        
        # Create PollCycle, CameraSnapshot, EntityStatus
        poll_cycle = PollCycle.objects.create()
        CameraSnapshot.objects.create(
            poll_cycle=poll_cycle,
            camera=camera,
            detected_emotion='happy',
            confidence_score=0.95
        )
        EntityStatus.objects.create(
            poll_cycle=poll_cycle,
            entity=entity,
            state_value='22.5'
        )

        self.client.login(username='testuser', password='password123')
        response = self.client.get(reverse('results_page') + "?download=csv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertTrue('attachment' in response['Content-Disposition'])
        self.assertTrue('emotion_analysis_results.csv' in response['Content-Disposition'])

        # Decode CSV content
        content = response.content.decode('utf-8')
        lines = content.splitlines()
        self.assertGreaterEqual(len(lines), 2)
        
        # Check header columns exist
        headers = lines[0].split(',')
        self.assertTrue("Living Room Camera_camera_id" in headers)
        self.assertTrue("Living Room Camera_name" in headers)
        self.assertTrue("Living Room Camera_location" in headers)
        self.assertTrue("Living Room Camera_image" in headers)
        self.assertTrue("Living Room Camera_detected_emotion" in headers)
        self.assertTrue("Living Room Camera_confidence_score" in headers)
        
        self.assertTrue("Temperature Sensor_entity_id" in headers)
        self.assertTrue("Temperature Sensor_name" in headers)
        self.assertTrue("Temperature Sensor_location" in headers)
        self.assertTrue("Temperature Sensor_unit_of_measurement" in headers)
        self.assertTrue("Temperature Sensor_state_value" in headers)

        # Check values row exists
        values = lines[1].split(',')
        self.assertTrue("camera.living_room" in values)
        self.assertTrue("Living Room Camera" in values)
        self.assertTrue("Living Room" in values)
        self.assertTrue("happy" in values)
        self.assertTrue("0.95" in values)
        self.assertTrue("sensor.temp" in values)
        self.assertTrue("Temperature Sensor" in values)
        self.assertTrue("22.5" in values)
