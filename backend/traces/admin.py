"""
Django Admin configuration for Message Trace models.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import MessageTraceLog, PullHistory


@admin.register(MessageTraceLog)
class MessageTraceLogAdmin(admin.ModelAdmin):
    list_display = [
        'received_date', 'sender', 'recipient', 'subject_truncated',
        'status_badge', 'direction', 'size_formatted', 'trace_date'
    ]
    list_filter = ['status', 'direction', 'received_date', 'trace_date']
    search_fields = ['sender', 'recipient', 'subject', 'message_id']
    readonly_fields = ['message_id', 'raw_json', 'event_data', 'created_at', 'updated_at']
    date_hierarchy = 'received_date'
    ordering = ['-received_date']

    fieldsets = (
        ('Message Information', {
            'fields': ('message_id', 'subject', 'sender', 'recipient')
        }),
        ('Delivery Details', {
            'fields': ('status', 'direction', 'size', 'received_date')
        }),
        ('Trace Data', {
            'fields': ('trace_date', 'event_data', 'raw_json'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def subject_truncated(self, obj):
        """Truncate long subjects for display."""
        if len(obj.subject) > 50:
            return f"{obj.subject[:50]}..."
        return obj.subject
    subject_truncated.short_description = 'Subject'

    def status_badge(self, obj):
        """Display status as a colored badge."""
        colors = {
            'Delivered': 'green',
            'Failed': 'red',
            'Pending': 'orange',
            'Quarantined': 'purple',
            'FilteredAsSpam': 'brown',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'

    def size_formatted(self, obj):
        """Format size in human-readable format."""
        size = obj.size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    size_formatted.short_description = 'Size'


@admin.register(PullHistory)
class PullHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'start_time', 'status_badge', 'trigger_type', 'records_pulled',
        'records_new', 'duration_display', 'triggered_by'
    ]
    list_filter = ['status', 'trigger_type', 'start_time']
    readonly_fields = [
        'start_time', 'end_time', 'pull_start_date', 'pull_end_date',
        'records_pulled', 'records_new', 'records_updated', 'error_message',
        'api_method', 'created_at'
    ]
    ordering = ['-start_time']

    def status_badge(self, obj):
        """Display status as a colored badge."""
        colors = {
            'Success': 'green',
            'Failed': 'red',
            'Running': 'blue',
            'Partial': 'orange',
            'Cancelled': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'

    def duration_display(self, obj):
        """Display duration in human-readable format."""
        duration = obj.duration_seconds
        if duration is None:
            return '-'
        if duration < 60:
            return f"{duration:.1f}s"
        minutes = duration // 60
        seconds = duration % 60
        return f"{int(minutes)}m {int(seconds)}s"
    duration_display.short_description = 'Duration'
