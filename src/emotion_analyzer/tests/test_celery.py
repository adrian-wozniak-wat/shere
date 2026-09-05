from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from emotion_analyzer.tasks import analyze_emotions

User = get_user_model()

class CeleryBeatControllerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client.login(username='testuser', password='password123')

    def test_run_page_renders_with_is_running_false(self):
        # Make sure no periodic task exists initially
        PeriodicTask.objects.all().delete()
        response = self.client.get(reverse('run_page'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'emotion_analyzer/run.html')
        self.assertEqual(response.context['is_running'], False)
        self.assertContains(response, 'Start')
        self.assertNotContains(response, 'Stop')

    def test_start_periodic_task(self):
        response = self.client.post(reverse('run_page'), {
            'action': 'start',
            'every': 30,
            'period': 'seconds'
        })
        self.assertRedirects(response, reverse('run_page'))
        
        self.assertEqual(PeriodicTask.objects.count(), 1)
        task = PeriodicTask.objects.first()
        self.assertEqual(task.name, 'Analyze Emotions Periodic Task')
        self.assertEqual(task.task, 'emotion_analyzer.tasks.analyze_emotions')
        self.assertTrue(task.enabled)
        self.assertEqual(task.interval.every, 30)
        self.assertEqual(task.interval.period, 'seconds')

        response = self.client.get(reverse('run_page'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['is_running'], True)
        self.assertContains(response, 'Stop')
        self.assertNotContains(response, 'Start')

    def test_start_periodic_task_with_custom_interval(self):
        response = self.client.post(reverse('run_page'), {
            'action': 'start',
            'every': 45,
            'period': 'minutes'
        })
        self.assertRedirects(response, reverse('run_page'))
        
        self.assertEqual(PeriodicTask.objects.count(), 1)
        task = PeriodicTask.objects.first()
        self.assertEqual(task.name, 'Analyze Emotions Periodic Task')
        self.assertTrue(task.enabled)
        self.assertEqual(task.interval.every, 45)
        self.assertEqual(task.interval.period, 'minutes')

    def test_stop_periodic_task(self):
        from django_celery_beat.models import PeriodicTasks
        schedule = IntervalSchedule.objects.create(every=30, period=IntervalSchedule.SECONDS)
        task = PeriodicTask.objects.create(
            name='Analyze Emotions Periodic Task',
            task='emotion_analyzer.tasks.analyze_emotions',
            interval=schedule,
            enabled=True
        )

        last_change_before = PeriodicTasks.last_change()

        response = self.client.post(reverse('run_page'), {
            'action': 'stop'
        })
        self.assertRedirects(response, reverse('run_page'))

        task.refresh_from_db()
        self.assertFalse(task.enabled)

        # Verify that the django-celery-beat's change tracking table has been updated
        self.assertGreater(PeriodicTasks.last_change(), last_change_before)

        response = self.client.get(reverse('run_page'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['is_running'], False)
        self.assertContains(response, 'Start')
        self.assertNotContains(response, 'Stop')

    @patch('emotion_analyzer.services.test_ha_connection.test_ha_connection')
    def test_run_page_action_test_success(self, mock_test_conn):
        mock_test_conn.return_value = None
        
        response = self.client.post(reverse('run_page'), {
            'action': 'test'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'emotion_analyzer/run.html')
        self.assertIsNotNone(response.context['test_result'])
        self.assertTrue(response.context['test_result']['overall_success'])
        self.assertContains(response, 'Diagnostic Results')
        self.assertContains(response, 'Home Assistant Credentials')
        self.assertContains(response, 'OK')

    @patch('emotion_analyzer.services.test_ha_connection.test_ha_connection')
    def test_run_page_action_test_failure(self, mock_test_conn):
        mock_test_conn.return_value = "Failed to connect to Home Assistant API at http://localhost:8123: Connection refused"
        
        response = self.client.post(reverse('run_page'), {
            'action': 'test'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'emotion_analyzer/run.html')
        self.assertIsNotNone(response.context['test_result'])
        self.assertFalse(response.context['test_result']['overall_success'])
        self.assertEqual(response.context['test_result']['error_message'], mock_test_conn.return_value)
        self.assertContains(response, 'Diagnostic Results')
        self.assertContains(response, 'FAILED')
        self.assertContains(response, 'Details:')


class CeleryTasksTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='taskuser', password='password123')

    @patch('emotion_analyzer.tasks.poll_ha_data')
    def test_analyze_emotions_task_success(self, mock_poll_ha):
        mock_poll_cycle = MagicMock()
        mock_poll_cycle.id = 42
        mock_poll_ha.return_value = mock_poll_cycle

        result = analyze_emotions()
        self.assertEqual(result, "Success: Polling cycle ID 42 created")
        mock_poll_ha.assert_called_once()

    @patch('emotion_analyzer.tasks.poll_ha_data')
    def test_analyze_emotions_task_skipped(self, mock_poll_ha):
        mock_poll_ha.return_value = None

        result = analyze_emotions()
        self.assertEqual(result, "Skipped: No Home Assistant credentials found")
        mock_poll_ha.assert_called_once()

    @patch('emotion_analyzer.tasks.poll_ha_data')
    def test_analyze_emotions_task_exception(self, mock_poll_ha):
        mock_poll_ha.side_effect = Exception("Database error")

        with self.assertRaises(Exception) as context:
            analyze_emotions()
        self.assertTrue("Database error" in str(context.exception))
