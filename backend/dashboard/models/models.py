from django.db import models
from django.utils import timezone
import uuid

class Sensor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    topic = models.CharField(max_length=200, unique=True)  # "smartclass/temp1"
    location = models.CharField(max_length=100, default="Classroom")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.topic})"

class SensorReading(models.Model):
    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name='readings')
    timestamp = models.DateTimeField(default=timezone.now)
    temperature = models.FloatField(null=True, blank=True)
    humidity = models.FloatField(null=True, blank=True)
    pressure = models.FloatField(null=True, blank=True)
    light = models.FloatField(null=True, blank=True)
    motion = models.BooleanField(default=False)
    
    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['sensor', 'timestamp']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.sensor.name}: {self.temperature}°C @ {self.timestamp}"
