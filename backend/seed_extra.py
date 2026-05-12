import os
import django
import random
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartclass.settings')
django.setup()

from dashboard.models import Rider, Helmet, Incident, MaintenanceLog

def seed_data():
    print("Seeding more platform data...")
    
    # Ensure at least one rider/helmet exists
    rider, _ = Rider.objects.get_or_create(
        email='john@example.com',
        defaults={'name': 'John Doe', 'bike_id': 'BIKE-001'}
    )
    
    # Try to find or assign a helmet
    helmet = Helmet.objects.filter(rider=rider).first()
    if not helmet:
        helmet, _ = Helmet.objects.get_or_create(
            helmet_id="HELMET-ALPHA",
            defaults={'rider': rider, 'is_connected': True}
        )

    # Seed Incidents
    types = ['CRASH', 'ALC', 'DISC']
    for _ in range(5):
        Incident.objects.create(
            rider=rider,
            helmet=helmet,
            type=random.choice(types),
            latitude=34.05,
            longitude=-118.24,
            resolved=random.choice([True, False])
        )

    # Seed Maintenance
    MaintenanceLog.objects.create(
        helmet=helmet,
        description="Routine sensor calibration and battery check.",
        technician="Tech #42",
        battery_replaced=True
    )
    
    print("Done! Data seeded for Incidents and Maintenance.")

if __name__ == "__main__":
    seed_data()