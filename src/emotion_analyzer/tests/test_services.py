import os
from django.conf import settings
from django.test import TestCase
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from emotion_analyzer.models import (
    HomeAssistantCredentials,
    Entity,
    Camera,
    PollCycle,
    CameraSnapshot,
    EntityStatus
)
from emotion_analyzer.services.poll_ha_data import poll_ha_data
from emotion_analyzer.services.test_ha_connection import test_ha_connection

from django.test import TestCase, override_settings
import shutil
import tempfile

User = get_user_model()
TEST_MEDIA_DIR = os.path.join(settings.BASE_DIR, 'temp_test_media')

@override_settings(MEDIA_ROOT=TEST_MEDIA_DIR)
class PollHADataTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='polluser', password='password123')
        os.makedirs(TEST_MEDIA_DIR, exist_ok=True)

    def tearDown(self):
        if os.path.exists(TEST_MEDIA_DIR):
            shutil.rmtree(TEST_MEDIA_DIR, ignore_errors=True)
        
    def test_poll_ha_data_no_credentials(self):
        # Ensure no credentials exist
        HomeAssistantCredentials.objects.all().delete()
        
        cycle = poll_ha_data()
        self.assertIsNone(cycle)
        self.assertEqual(PollCycle.objects.count(), 0)

    @patch('emotion_analyzer.services.poll_ha_data.get_entity_data')
    @patch('emotion_analyzer.services.poll_ha_data.analyze_emotion')
    @patch('emotion_analyzer.services.poll_ha_data.save_camera_snapshot')
    def test_poll_ha_data_success(self, mock_save_camera_snapshot, mock_analyze_emotion, mock_get_entity_data):
        # Create credentials
        cred = HomeAssistantCredentials.objects.create(
            user=self.user,
            username='ha_user',
            host='192.168.1.10',
            port=8123
        )
        cred.token = 'mocked_token'
        cred.save()
        
        # Create a Camera and an Entity
        camera = Camera.objects.create(camera_id='camera.front_door', location='Front Door')
        entity = Entity.objects.create(entity_id='sensor.temperature', location='Living Room')
        
        # Setup mocks
        mock_save_camera_snapshot.return_value = '/dummy/path/frame_camera.front_door.jpg'
        mock_analyze_emotion.return_value = ('happy', 0.92, 45, 120)
        mock_get_entity_data.return_value = ('22.5', {'unit_of_measurement': '°C'})
        
        # Run poll
        cycle = poll_ha_data()
        
        self.assertIsNotNone(cycle)
        self.assertEqual(PollCycle.objects.count(), 1)
        self.assertEqual(cycle.statuses.count(), 1)
        self.assertEqual(cycle.snapshots.count(), 1)
        self.assertIsNotNone(cycle.cycle_length_milliseconds)
        self.assertEqual(cycle.face_recognition_milliseconds, 45)
        self.assertEqual(cycle.emotion_recognition_milliseconds, 120)
        
        # Verify EntityStatus
        status = cycle.statuses.first()
        self.assertEqual(status.entity, entity)
        self.assertEqual(status.state_value, '22.5')
        
        # Verify CameraSnapshot
        snapshot = cycle.snapshots.first()
        self.assertEqual(snapshot.camera, camera)
        self.assertEqual(snapshot.detected_emotion, 'happy')
        self.assertEqual(snapshot.confidence_score, 0.92)
        self.assertEqual(snapshot.face_recognition_milliseconds, 45)
        self.assertEqual(snapshot.emotion_recognition_milliseconds, 120)
        self.assertFalse(snapshot.image)  # Since no file was physically written to disk by the mock
        
        # Verify calls to mocks
        mock_get_entity_data.assert_called_once_with(
            ha_url='http://192.168.1.10:8123',
            token='mocked_token',
            entity_id='sensor.temperature'
        )
        mock_save_camera_snapshot.assert_called_once()
        mock_analyze_emotion.assert_called_once_with('/dummy/path/frame_camera.front_door.jpg')
        
        # Now let's test file path resolution when file is written.
        # We can trigger another poll, and mock save_camera_snapshot to create a dummy file.
        def mock_save_side_effect(ha_url, camera_entity, files_directory, timestamp, token):
            os.makedirs(files_directory, exist_ok=True)
            dummy_file = os.path.join(files_directory, f"frame_{timestamp}.jpg")
            with open(dummy_file, 'wb') as f:
                f.write(b'dummy jpeg data')
            return dummy_file
            
        mock_save_camera_snapshot.side_effect = mock_save_side_effect
        mock_save_camera_snapshot.reset_mock()
        
        mock_analyze_emotion.reset_mock()
        mock_analyze_emotion.side_effect = None
        mock_analyze_emotion.return_value = ('sad', 0.75, 50, 110)
        
        cycle2 = poll_ha_data()
        self.assertIsNotNone(cycle2)
        snapshot2 = cycle2.snapshots.first()
        self.assertEqual(snapshot2.detected_emotion, 'sad')
        self.assertEqual(snapshot2.confidence_score, 0.75)
        self.assertEqual(snapshot2.face_recognition_milliseconds, 50)
        self.assertEqual(snapshot2.emotion_recognition_milliseconds, 110)
        self.assertIsNotNone(snapshot2.image)
        self.assertTrue(snapshot2.image.name.startswith('camera_snapshots/'))
        
        # Cleanup dummy file
        if snapshot2.image:
            media_root = getattr(settings, 'MEDIA_ROOT', os.path.join(settings.BASE_DIR, 'media'))
            full_path = os.path.join(media_root, snapshot2.image.name)
            if os.path.exists(full_path):
                os.remove(full_path)

    @patch('emotion_analyzer.services.poll_ha_data.get_entity_data')
    @patch('emotion_analyzer.services.poll_ha_data.analyze_emotion')
    @patch('emotion_analyzer.services.poll_ha_data.save_camera_snapshot')
    def test_poll_ha_data_no_face_detected(self, mock_save_camera_snapshot, mock_analyze_emotion, mock_get_entity_data):
        cred = HomeAssistantCredentials.objects.create(
            user=self.user, username='ha_user', host='192.168.1.10', port=8123
        )
        cred.token = 'mocked_token'
        cred.save()
        
        camera = Camera.objects.create(camera_id='camera.living_room', location='Living Room')
        
        mock_save_camera_snapshot.return_value = '/dummy/path/frame.jpg'
        mock_analyze_emotion.return_value = ('none', 0.0, 35, None)
        mock_get_entity_data.return_value = ('on', {})

        cycle = poll_ha_data()
        self.assertIsNotNone(cycle)
        self.assertIsNotNone(cycle.cycle_length_milliseconds)
        self.assertEqual(cycle.face_recognition_milliseconds, 35)
        self.assertIsNone(cycle.emotion_recognition_milliseconds)

        snapshot = cycle.snapshots.first()
        self.assertEqual(snapshot.face_recognition_milliseconds, 35)
        self.assertIsNone(snapshot.emotion_recognition_milliseconds)


class SaveCameraSnapshotTest(TestCase):
    @patch('emotion_analyzer.services.analyze_emotion.requests.get')
    def test_save_camera_snapshot_naming_scheme(self, mock_get):
        from emotion_analyzer.services.analyze_emotion import save_camera_snapshot
        import shutil
        import datetime

        # Setup mock response
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        import cv2
        import numpy as np
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        _, img_encoded = cv2.imencode('.jpg', img)
        mock_response.content = img_encoded.tobytes()
        mock_get.return_value = mock_response

        # Call function
        temp_dir = os.path.join(settings.BASE_DIR, 'media', 'temp_test_snapshots')
        timestamp = "1782142245_camera.test"
        
        try:
            saved_path = save_camera_snapshot(
                ha_url="http://dummy",
                camera_entity="camera.test",
                files_directory=temp_dir,
                timestamp=timestamp,
                token="dummy_token"
            )
            
            self.assertIsNotNone(saved_path)
            
            dt = datetime.datetime.fromtimestamp(1782142245, tz=datetime.timezone.utc)
            expected_suffix = os.path.join(dt.strftime('%H'), dt.strftime('%M'), dt.strftime('%S'), f"frame_{timestamp}.jpg")
            self.assertTrue(saved_path.endswith(expected_suffix), f"Path {saved_path} does not end with {expected_suffix}")
            self.assertTrue(os.path.exists(saved_path))
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)


class TestHAConnectionServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')

    def test_no_credentials(self):
        HomeAssistantCredentials.objects.all().delete()
        res = test_ha_connection()
        self.assertIn("No credentials found in database", res)

    @patch('emotion_analyzer.services.test_ha_connection.requests.get')
    def test_failed_general_connectivity(self, mock_get):
        cred = HomeAssistantCredentials.objects.create(
            user=self.user, username='ha_user', host='192.168.1.10', port=8123
        )
        cred.token = 'mocked_token'
        cred.save()

        mock_get.side_effect = Exception("Connection refused")
        res = test_ha_connection()
        self.assertIn("Failed to connect to Home Assistant API", res)

    @patch('emotion_analyzer.services.test_ha_connection.get_entity_data')
    @patch('emotion_analyzer.services.test_ha_connection.requests.get')
    def test_entity_polling_failure(self, mock_get, mock_get_entity):
        cred = HomeAssistantCredentials.objects.create(
            user=self.user, username='ha_user', host='192.168.1.10', port=8123
        )
        cred.token = 'mocked_token'
        cred.save()
        
        Entity.objects.create(entity_id='sensor.temperature', location='Living Room')

        # Mock general API check to succeed
        mock_response = mock_get.return_value
        mock_response.raise_for_status.return_value = None

        mock_get_entity.side_effect = Exception("Entity not found")
        res = test_ha_connection()
        self.assertIn("Failed to poll entity data for sensor.temperature", res)

    @patch('emotion_analyzer.services.test_ha_connection.analyze_emotion')
    @patch('emotion_analyzer.services.test_ha_connection.get_entity_data')
    @patch('emotion_analyzer.services.test_ha_connection.requests.get')
    def test_success_with_dummy_image_when_no_cameras(self, mock_get, mock_get_entity, mock_analyze_emotion):
        cred = HomeAssistantCredentials.objects.create(
            user=self.user, username='ha_user', host='192.168.1.10', port=8123
        )
        cred.token = 'mocked_token'
        cred.save()
        
        Entity.objects.create(entity_id='sensor.temperature', location='Living Room')

        # Mock general API check
        mock_response = mock_get.return_value
        mock_response.raise_for_status.return_value = None

        mock_get_entity.return_value = ('22.5', {})
        
        mock_analyze_emotion.return_value = ('neutral', 0.80, 50, 100)

        res = test_ha_connection()
        self.assertIsNone(res)
        mock_analyze_emotion.assert_called_once()

    @patch('emotion_analyzer.services.test_ha_connection.analyze_emotion')
    @patch('emotion_analyzer.services.test_ha_connection.get_entity_data')
    @patch('emotion_analyzer.services.test_ha_connection.requests.get')
    def test_success_with_camera(self, mock_get, mock_get_entity, mock_analyze_emotion):
        cred = HomeAssistantCredentials.objects.create(
            user=self.user, username='ha_user', host='192.168.1.10', port=8123
        )
        cred.token = 'mocked_token'
        cred.save()
        
        Entity.objects.create(entity_id='sensor.temperature', location='Living Room')
        Camera.objects.create(camera_id='camera.front_door', location='Front Door')

        mock_resp_api = MagicMock()
        mock_resp_api.raise_for_status.return_value = None
        
        mock_resp_cam = MagicMock()
        mock_resp_cam.raise_for_status.return_value = None
        
        import cv2
        import numpy as np
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        _, img_encoded = cv2.imencode('.jpg', img)
        mock_resp_cam.content = img_encoded.tobytes()

        mock_get.side_effect = [mock_resp_api, mock_resp_cam]
        mock_get_entity.return_value = ('22.5', {})
        
        mock_analyze_emotion.return_value = ('neutral', 0.80, 50, 100)

        res = test_ha_connection()
        self.assertIsNone(res)
        mock_analyze_emotion.assert_called_once()


class AnalyzeEmotionYOLOTest(TestCase):
    @patch('emotion_analyzer.services.analyze_emotion.get_emotion_pipeline')
    @patch('emotion_analyzer.services.analyze_emotion.get_face_detector')
    def test_analyze_emotion_face_found(self, mock_get_face_detector, mock_get_emotion_pipeline):
        from emotion_analyzer.services.analyze_emotion import analyze_emotion
        import numpy as np
        from PIL import Image
        import shutil

        # Setup mock face detector and its output
        mock_detector = MagicMock()
        mock_get_face_detector.return_value = mock_detector
        
        # Mock result of detector: a list containing a Results object
        mock_result = MagicMock()
        
        # Box coordinate mocks
        mock_box = MagicMock()
        mock_box.xyxy = [MagicMock()]
        mock_box.xyxy[0].tolist.return_value = [10.0, 20.0, 80.0, 90.0]
        
        mock_result.boxes = [mock_box]
        mock_detector.return_value = [mock_result]

        # Setup mock emotion pipeline predictions
        mock_pipe = MagicMock()
        mock_pipe.return_value = [{"label": "happy", "score": 0.95}]
        mock_get_emotion_pipeline.return_value = mock_pipe

        # Create a dummy image file
        temp_dir = os.path.join(settings.BASE_DIR, 'media', 'temp_test_analyze')
        os.makedirs(temp_dir, exist_ok=True)
        img_path = os.path.join(temp_dir, 'test_scene.jpg')
        
        try:
            # Create a 100x100 RGB image and save it
            img = Image.new('RGB', (100, 100), color='red')
            img.save(img_path)

            emotion, confidence, face_ms, emotion_ms = analyze_emotion(img_path)
            
            self.assertEqual(emotion, 'happy')
            self.assertEqual(confidence, 0.95)
            self.assertIsNotNone(face_ms)
            self.assertIsNotNone(emotion_ms)
            
            # Check that a cropped face image was saved
            expected_crop_path = os.path.join(temp_dir, 'test_scene_face_cropped.jpg')
            self.assertTrue(os.path.exists(expected_crop_path))
            
            # Check that the cropped image is indeed cropped to the bounding box (70x70)
            cropped_img = Image.open(expected_crop_path)
            self.assertEqual(cropped_img.size, (70, 70))  # 80 - 10 = 70, 90 - 20 = 70
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    @patch('emotion_analyzer.services.analyze_emotion.get_emotion_pipeline')
    @patch('emotion_analyzer.services.analyze_emotion.get_face_detector')
    def test_analyze_emotion_no_face_found(self, mock_get_face_detector, mock_get_emotion_pipeline):
        from emotion_analyzer.services.analyze_emotion import analyze_emotion
        from PIL import Image

        # Setup mock face detector returning no boxes
        mock_detector = MagicMock()
        mock_get_face_detector.return_value = mock_detector
        
        mock_result = MagicMock()
        mock_result.boxes = []
        mock_detector.return_value = [mock_result]

        # Setup mock emotion pipeline predictions
        mock_pipe = MagicMock()
        mock_pipe.return_value = [{"label": "sad", "score": 0.88}]
        mock_get_emotion_pipeline.return_value = mock_pipe

        # Pass a PIL image directly
        img = Image.new('RGB', (100, 100), color='blue')
        emotion, confidence, face_ms, emotion_ms = analyze_emotion(img)
        
        self.assertEqual(emotion, 'none')
        self.assertEqual(confidence, 0.0)
        self.assertIsNotNone(face_ms)
        self.assertIsNone(emotion_ms)

    @patch('emotion_analyzer.services.analyze_emotion.get_emotion_pipeline')
    @patch('emotion_analyzer.services.analyze_emotion.get_face_detector')
    def test_analyze_emotion_detector_fails(self, mock_get_face_detector, mock_get_emotion_pipeline):
        from emotion_analyzer.services.analyze_emotion import analyze_emotion
        from PIL import Image

        # Setup mock face detector raising an exception
        mock_detector = MagicMock()
        mock_detector.side_effect = RuntimeError("YOLO fails")
        mock_get_face_detector.return_value = mock_detector

        # Setup mock emotion pipeline predictions
        mock_pipe = MagicMock()
        mock_pipe.return_value = [{"label": "neutral", "score": 0.77}]
        mock_get_emotion_pipeline.return_value = mock_pipe

        # Pass a PIL image directly
        img = Image.new('RGB', (100, 100), color='green')
        emotion, confidence, face_ms, emotion_ms = analyze_emotion(img)
        
        # Should return 'none' and 0.0
        self.assertEqual(emotion, 'none')
        self.assertEqual(confidence, 0.0)
        self.assertIsNotNone(face_ms)
        self.assertIsNone(emotion_ms)
