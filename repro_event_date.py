
import os
import django
from datetime import datetime, timedelta
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "choirbackend.settings.development")
django.setup()

from rest_framework.test import APIRequestFactory

from authentication.models import User
from core.models import Organization
from events.serializers import EventCreateSerializer
from events.models import Event
from django.utils import timezone

def test_event_date_creation():
    print(f"Server Timezone Config: {django.conf.settings.TIME_ZONE}")
    print(f"Current Time (now): {timezone.now()}")
    print(f"Current Time (local): {timezone.localtime(timezone.now())}")

    print("Setting up test data...")
    # Clean up
    User.objects.filter(email='test_event_date@example.com').delete()
    Organization.objects.filter(name='Test Org for Dates').delete()
    Event.objects.filter(slug__startswith='test-event-date').delete()

    # Create Org & User
    org = Organization.objects.create(name='Test Org for Dates', slug='test-org-dates', code='TEST')
    user = User.objects.create_user(
        username='test_event_date',
        email='test_event_date@example.com',
        password='password123',
        organization=org
    )

    # Mock Request
    factory = APIRequestFactory()
    request = factory.post('/api/events/')
    request.user = user

    # Test Case 1: Naive Datetime string
    print("\n--- Test Case 1: Naive Datetime String '2026-05-15 10:00:00' ---")
    data_naive = {
        'title': 'Test Event Naive',
        'event_type': 'rehearsal',
        'start_datetime': '2026-05-15 10:00:00', # No TZ
        'end_datetime': '2026-05-15 12:00:00',
        'is_mandatory': True
    }
    
    serializer = EventCreateSerializer(data=data_naive, context={'request': request})
    if serializer.is_valid():
        event = serializer.save()
        print(f"Input: {data_naive['start_datetime']}")
        print(f"Saved: {event.start_datetime} (TZ: {event.start_datetime.tzinfo})")
    else:
        print(f"Validation Error: {serializer.errors}")

    # Test Case 4: Date Only String '2026-05-15'
    print("\n--- Test Case 4: Date Only String '2026-05-15' ---")
    data_date = {
        'title': 'Test Event Date Only',
        'event_type': 'rehearsal',
        'start_datetime': '2026-05-15', 
        'end_datetime': None,
        'is_mandatory': True
    }
    
    serializer = EventCreateSerializer(data=data_date, context={'request': request})
    if serializer.is_valid():
        event = serializer.save()
        print(f"Input: {data_date['start_datetime']}")
        print(f"Saved: {event.start_datetime} (TZ: {event.start_datetime.tzinfo})")
    else:
         print(f"Validation Error: {serializer.errors}")
    print("\n--- Test Case 2: ISO String '2026-05-15T10:00:00Z' ---")
    data_utc = {
        'title': 'Test Event UTC',
        'event_type': 'rehearsal',
        'start_datetime': '2026-05-15T10:00:00Z', 
        'end_datetime': '2026-05-15T12:00:00Z',
        'is_mandatory': True
    }
    
    serializer = EventCreateSerializer(data=data_utc, context={'request': request})
    if serializer.is_valid():
        event = serializer.save()
        print(f"Input: {data_utc['start_datetime']}")
        print(f"Saved: {event.start_datetime}")
    else:
         print(f"Validation Error: {serializer.errors}")

    # Test Case 3: ISO String with Offset +01:00
    print("\n--- Test Case 3: ISO String '2026-05-15T10:00:00+01:00' ---")
    data_offset = {
        'title': 'Test Event Offset',
        'event_type': 'rehearsal',
        'start_datetime': '2026-05-15T10:00:00+01:00', 
        'end_datetime': '2026-05-15T12:00:00+01:00',
        'is_mandatory': True
    }
    
    serializer = EventCreateSerializer(data=data_offset, context={'request': request})
    if serializer.is_valid():
        event = serializer.save()
        print(f"Input: {data_offset['start_datetime']}")
        print(f"Saved: {event.start_datetime} (Converted to UTC/Server Time)")
    else:
         print(f"Validation Error: {serializer.errors}")

if __name__ == "__main__":
    try:
        test_event_date_creation()
    except Exception as e:
        print(f"Error: {e}")
