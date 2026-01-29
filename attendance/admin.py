from django.contrib import admin
from attendance.models import Event, EventAttendance


class EventAttendanceInline(admin.TabularInline):
    """Inline display of attendance in Event admin"""
    model = EventAttendance
    extra = 0
    readonly_fields = ['user', 'status', 'marked_by', 'marked_at', 'notes']
    fields = readonly_fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'organization', 'event_type', 'status',
        'start_datetime', 'is_mandatory', 'attendance_count'
    ]
    list_filter = ['organization', 'event_type', 'status', 'is_mandatory', 'start_datetime']
    search_fields = ['title', 'description', 'location', 'organization__name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'attendance_count']
    inlines = [EventAttendanceInline]
    date_hierarchy = 'start_datetime'

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'organization', 'title', 'description', 'event_type')
        }),
        ('Schedule', {
            'fields': ('start_datetime', 'end_datetime', 'location')
        }),
        ('Settings', {
            'fields': ('is_mandatory', 'target_voice_parts', 'status')
        }),
        ('Metadata', {
            'fields': ('created_by', 'attendance_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def attendance_count(self, obj):
        """Display count of attendance records"""
        return obj.attendances.count()
    attendance_count.short_description = 'Attendance Records'


@admin.register(EventAttendance)
class EventAttendanceAdmin(admin.ModelAdmin):
    list_display = [
        'event', 'user', 'status', 'marked_by', 'marked_at'
    ]
    list_filter = ['status', 'event__organization', 'event__event_type', 'marked_at']
    search_fields = [
        'event__title', 'user__email', 'user__first_name', 'user__last_name',
        'marked_by__email'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at', 'marked_at']

    fieldsets = (
        ('Attendance Record', {
            'fields': ('id', 'event', 'user', 'status')
        }),
        ('Marking Info', {
            'fields': ('marked_by', 'marked_at', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
