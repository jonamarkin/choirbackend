from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from attendance.models import EventAttendance, get_user_attendance_stats
from core.models import Organization
from events.models import Event

User = get_user_model()


class AttendanceStatsTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name='Test Org',
            slug='test-org',
            contact_email='org@test.com',
            contact_phone='1234567890',
            code='4321',
        )
        self.user = User.objects.create_user(
            username='member1',
            email='member1@test.com',
            password='password123',
            organization=self.org,
            member_part='soprano',
            is_active=True,
        )

    def test_stats_include_past_started_event_even_if_not_completed(self):
        start = timezone.now() - timedelta(days=1)
        event = Event.objects.create(
            organization=self.org,
            title='Weekly Rehearsal',
            event_type='rehearsal',
            start_datetime=start,
            end_datetime=start + timedelta(hours=2),
            is_mandatory=True,
            status='scheduled',
            target_voice_parts=None,
        )
        EventAttendance.objects.create(
            event=event,
            user=self.user,
            status='present',
            marked_by=self.user,
        )

        stats = get_user_attendance_stats(self.user)

        self.assertEqual(stats['total_mandatory_events'], 1)
        self.assertEqual(stats['events_attended'], 1)
        self.assertEqual(stats['present'], 1)
        self.assertEqual(stats['attendance_percentage'], 100.0)

    def test_stats_respect_all_and_specific_voice_part_targets(self):
        start = timezone.now() - timedelta(days=2)
        event_all = Event.objects.create(
            organization=self.org,
            title='General Meeting',
            event_type='rehearsal',
            start_datetime=start,
            end_datetime=start + timedelta(hours=2),
            is_mandatory=True,
            status='completed',
            target_voice_parts=['all'],
        )
        event_other_part = Event.objects.create(
            organization=self.org,
            title='Alto Session',
            event_type='rehearsal',
            start_datetime=start,
            end_datetime=start + timedelta(hours=2),
            is_mandatory=True,
            status='completed',
            target_voice_parts=['alto'],
        )

        EventAttendance.objects.create(
            event=event_all,
            user=self.user,
            status='late',
            marked_by=self.user,
        )
        EventAttendance.objects.create(
            event=event_other_part,
            user=self.user,
            status='present',
            marked_by=self.user,
        )

        stats = get_user_attendance_stats(self.user)

        self.assertEqual(stats['total_mandatory_events'], 1)
        self.assertEqual(stats['events_attended'], 1)
        self.assertEqual(stats['late'], 1)
