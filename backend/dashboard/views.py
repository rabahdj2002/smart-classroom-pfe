import json
from django.shortcuts import render
from django.http import StreamingHttpResponse
from .models import SensorReading
from django.utils import timezone
import time

def dashboard(request):
    sensors = SensorReading.objects.values('sensor__name').distinct()
    return render(request, 'dashboard.html', {'sensors': sensors})

def live_data(request):
    def event_stream():
        while True:
            readings = list(SensorReading.objects.select_related('sensor')
                          .order_by('-timestamp')[:10])
            data = [{
                'timestamp': r.timestamp.strftime('%H:%M:%S'),
                'sensor': r.sensor.name,
                'temperature': r.temperature,
                'humidity': r.humidity,
                'pressure': r.pressure,
            } for r in readings]
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(1)
    
    return StreamingHttpResponse(event_stream(), content_type='text/event-stream',
                               headers={'Cache-Control': 'no-cache'})
