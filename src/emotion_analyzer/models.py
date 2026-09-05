from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet

class HomeAssistantCredentials(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    username = models.CharField(max_length=255)
    host = models.CharField(max_length=255, default='localhost')
    port = models.IntegerField(default=8123)
    _encrypted_token = models.TextField(db_column='encrypted_token')
    @property
    def token(self):
        """Decrypts and returns the plaintext token."""
        f = Fernet(settings.ENCRYPTION_KEY.encode())
        decrypted_bytes = f.decrypt(self._encrypted_token.encode())
        return decrypted_bytes.decode()
    @token.setter
    def token(self, plaintext_token):
        """Encrypts the plaintext token before storing it."""
        f = Fernet(settings.ENCRYPTION_KEY.encode())
        encrypted_bytes = f.encrypt(plaintext_token.encode())
        self._encrypted_token = encrypted_bytes.decode()

class PollCycle(models.Model):
    """The central heartbeat. Every 5 seconds, one of these is created."""
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    cycle_length_milliseconds = models.IntegerField(blank=True, null=True)
    face_recognition_milliseconds = models.IntegerField(blank=True, null=True)
    emotion_recognition_milliseconds = models.IntegerField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Poll Cycle at {self.timestamp}"

class Entity(models.Model):
    """Represents a Home Assistant entity."""
    entity_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255, default='', blank=True)
    location = models.CharField(max_length=255)
    unit_of_measurement = models.CharField(max_length=50, blank=True, null=True)
    def __str__(self):
        return f"{self.name or self.entity_id} ({self.location})"

class EntityStatus(models.Model):
    """Linked to the master poll cycle instead of having its own timestamp."""
    poll_cycle = models.ForeignKey(PollCycle, on_delete=models.CASCADE, related_name='statuses')
    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name='statuses')
    state_value = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.entity.entity_id}: {self.state_value}"


class Camera(models.Model):
    """The camera device itself."""
    camera_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255, default='', blank=True)
    location = models.CharField(max_length=255)


    def __str__(self):
        return self.name or self.location


class CameraSnapshot(models.Model):
    """Linked to BOTH the specific camera and the master poll cycle."""
    poll_cycle = models.ForeignKey(PollCycle, on_delete=models.CASCADE, related_name='snapshots')
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name='snapshots')
    image = models.ImageField(upload_to='camera_snapshots/%Y/%m/%d/', max_length=512, blank=True, null=True)
    detected_emotion = models.CharField(max_length=50, blank=True, null=True)
    confidence_score = models.FloatField(blank=True, null=True)
    face_recognition_milliseconds = models.IntegerField(blank=True, null=True)
    emotion_recognition_milliseconds = models.IntegerField(blank=True, null=True)


    def __str__(self):
        return f"{self.camera.location} snapshot at cycle {self.poll_cycle.id}"