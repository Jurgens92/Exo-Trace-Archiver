"""
Django REST Framework serializers for Message Trace models.

These serializers handle:
1. Data validation
2. JSON serialization/deserialization
3. Nested representations
"""

from rest_framework import serializers
from django.utils import timezone
from .models import MessageTraceLog, PullHistory


class MessageTraceLogSerializer(serializers.ModelSerializer):
    """
    Serializer for MessageTraceLog model.

    Includes computed fields for frontend display and filtering.
    """

    # Computed fields for display
    size_formatted = serializers.SerializerMethodField()
    duration_since_received = serializers.SerializerMethodField()

    class Meta:
        model = MessageTraceLog
        fields = [
            'id', 'message_id', 'received_date', 'sender', 'recipient',
            'subject', 'status', 'direction', 'size', 'size_formatted',
            'event_data', 'trace_date', 'created_at', 'updated_at',
            'duration_since_received'
        ]
        read_only_fields = fields  # All fields are read-only (data comes from API)

    def get_size_formatted(self, obj) -> str:
        """Format size in human-readable format."""
        size = obj.size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def get_duration_since_received(self, obj) -> str:
        """Get human-readable duration since message was received."""
        delta = timezone.now() - obj.received_date
        if delta.days > 0:
            return f"{delta.days} days ago"
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours} hours ago"
        minutes = delta.seconds // 60
        return f"{minutes} minutes ago"


class MessageTraceLogDetailSerializer(MessageTraceLogSerializer):
    """
    Detailed serializer including raw JSON for single record view.
    """

    class Meta(MessageTraceLogSerializer.Meta):
        fields = MessageTraceLogSerializer.Meta.fields + ['raw_json']


class MessageTraceLogListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list views (excludes heavy fields).
    """

    size_formatted = serializers.SerializerMethodField()

    class Meta:
        model = MessageTraceLog
        fields = [
            'id', 'message_id', 'received_date', 'sender', 'recipient',
            'subject', 'status', 'direction', 'size', 'size_formatted'
        ]
        read_only_fields = fields

    def get_size_formatted(self, obj) -> str:
        size = obj.size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class PullHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for PullHistory model.
    """

    duration_formatted = serializers.SerializerMethodField()

    class Meta:
        model = PullHistory
        fields = [
            'id', 'start_time', 'end_time', 'pull_start_date', 'pull_end_date',
            'records_pulled', 'records_new', 'records_updated', 'status',
            'error_message', 'trigger_type', 'triggered_by', 'api_method',
            'duration_formatted', 'created_at'
        ]
        read_only_fields = fields

    def get_duration_formatted(self, obj) -> str | None:
        """Format duration in human-readable format."""
        duration = obj.duration_seconds
        if duration is None:
            return None
        if duration < 60:
            return f"{duration:.1f}s"
        minutes = duration // 60
        seconds = duration % 60
        return f"{int(minutes)}m {int(seconds)}s"


class ManualPullRequestSerializer(serializers.Serializer):
    """
    Serializer for manual pull request validation.
    """

    start_date = serializers.DateTimeField(
        required=False,
        help_text="Start of date range to pull (default: yesterday 00:00 UTC)"
    )
    end_date = serializers.DateTimeField(
        required=False,
        help_text="End of date range to pull (default: yesterday 23:59 UTC)"
    )

    def validate(self, data):
        """Validate date range."""
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        if start_date and end_date and start_date >= end_date:
            raise serializers.ValidationError(
                "start_date must be before end_date"
            )

        # Exchange Online only keeps traces for 10 days
        if start_date:
            min_date = timezone.now() - timezone.timedelta(days=10)
            if start_date < min_date:
                raise serializers.ValidationError(
                    "start_date cannot be more than 10 days ago "
                    "(Exchange Online retention limit)"
                )

        return data


class DashboardStatsSerializer(serializers.Serializer):
    """
    Serializer for dashboard statistics.
    """

    total_traces = serializers.IntegerField()
    traces_today = serializers.IntegerField()
    traces_this_week = serializers.IntegerField()
    last_pull = serializers.SerializerMethodField()

    # Status breakdown
    delivered_count = serializers.IntegerField()
    failed_count = serializers.IntegerField()
    pending_count = serializers.IntegerField()
    quarantined_count = serializers.IntegerField()

    # Direction breakdown
    inbound_count = serializers.IntegerField()
    outbound_count = serializers.IntegerField()
    internal_count = serializers.IntegerField()

    # Recent activity
    recent_pulls = PullHistorySerializer(many=True)

    def get_last_pull(self, obj):
        last_pull = obj.get('last_pull')
        if last_pull:
            return PullHistorySerializer(last_pull).data
        return None
