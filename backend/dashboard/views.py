import json
import time
from django.http import StreamingHttpResponse
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from django.views.decorators.cache import cache_page
import random

@require_http_methods(["GET"])
def live_sensors(request):
    def event_stream():
        counter = 0
        while True:
            sensor_data = {
                'timestamp': time.strftime('%H:%M:%S'),
                'temperature': round(random.uniform(20, 35), 1),
                'pressure': round(random.uniform(1.8, 2.5), 1),
                'humidity': round(random.uniform(40, 70), 1),
                'counter': counter
            }
            yield f"data: {json.dumps(sensor_data)}\n\n"
            counter += 1
            time.sleep(1)
    
    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['Connection'] = 'keep-alive'
    return response

def dashboard(request):
    return render(request, 'dashboard.html')