"""
Django Filter classes for Message Trace API filtering.

These filters enable advanced querying of message trace logs
via URL query parameters.
"""

import django_filters
from django.db.models import Q
from .models import MessageTraceLog, PullHistory


class MessageTraceLogFilter(django_filters.FilterSet):
    """
    Filter for MessageTraceLog queryset.

    Supports filtering by:
    - Date range (start_date, end_date)
    - Sender (exact or contains)
    - Recipient (exact or contains)
    - Status
    - Direction
    - Subject (contains)
    - General search (sender, recipient, or subject)
    """

    # Date range filters
    start_date = django_filters.DateTimeFilter(
        field_name='received_date',
        lookup_expr='gte',
        help_text='Filter messages received on or after this date'
    )
    end_date = django_filters.DateTimeFilter(
        field_name='received_date',
        lookup_expr='lte',
        help_text='Filter messages received on or before this date'
    )

    # Sender filters
    sender = django_filters.CharFilter(
        field_name='sender',
        lookup_expr='iexact',
        help_text='Exact sender email (case-insensitive)'
    )
    sender_contains = django_filters.CharFilter(
        field_name='sender',
        lookup_expr='icontains',
        help_text='Sender email contains'
    )
    sender_domain = django_filters.CharFilter(
        method='filter_sender_domain',
        help_text='Sender domain'
    )

    # Recipient filters
    recipient = django_filters.CharFilter(
        field_name='recipient',
        lookup_expr='iexact',
        help_text='Exact recipient email (case-insensitive)'
    )
    recipient_contains = django_filters.CharFilter(
        field_name='recipient',
        lookup_expr='icontains',
        help_text='Recipient email contains'
    )
    recipient_domain = django_filters.CharFilter(
        method='filter_recipient_domain',
        help_text='Recipient domain'
    )

    # Subject filter
    subject = django_filters.CharFilter(
        field_name='subject',
        lookup_expr='icontains',
        help_text='Subject contains'
    )

    # Status and direction
    status = django_filters.ChoiceFilter(
        choices=MessageTraceLog.Status.choices,
        help_text='Delivery status'
    )
    direction = django_filters.ChoiceFilter(
        choices=MessageTraceLog.Direction.choices,
        help_text='Message direction'
    )

    # General search
    search = django_filters.CharFilter(
        method='filter_search',
        help_text='Search in sender, recipient, subject, or message_id'
    )

    # Trace date filter (when we pulled the data)
    trace_start = django_filters.DateTimeFilter(
        field_name='trace_date',
        lookup_expr='gte'
    )
    trace_end = django_filters.DateTimeFilter(
        field_name='trace_date',
        lookup_expr='lte'
    )

    class Meta:
        model = MessageTraceLog
        fields = [
            'start_date', 'end_date', 'sender', 'sender_contains',
            'sender_domain', 'recipient', 'recipient_contains',
            'recipient_domain', 'subject', 'status', 'direction',
            'search', 'trace_start', 'trace_end'
        ]

    def filter_sender_domain(self, queryset, name, value):
        """Filter by sender's email domain."""
        return queryset.filter(sender__iendswith=f'@{value}')

    def filter_recipient_domain(self, queryset, name, value):
        """Filter by recipient's email domain."""
        return queryset.filter(recipient__iendswith=f'@{value}')

    def filter_search(self, queryset, name, value):
        """
        General search across multiple fields.
        Useful for the frontend search box.
        """
        return queryset.filter(
            Q(sender__icontains=value) |
            Q(recipient__icontains=value) |
            Q(subject__icontains=value) |
            Q(message_id__icontains=value)
        )


class PullHistoryFilter(django_filters.FilterSet):
    """
    Filter for PullHistory queryset.
    """

    start_date = django_filters.DateTimeFilter(
        field_name='start_time',
        lookup_expr='gte'
    )
    end_date = django_filters.DateTimeFilter(
        field_name='start_time',
        lookup_expr='lte'
    )
    status = django_filters.ChoiceFilter(
        choices=PullHistory.Status.choices
    )
    trigger_type = django_filters.ChoiceFilter(
        choices=PullHistory.TriggerType.choices
    )

    class Meta:
        model = PullHistory
        fields = ['start_date', 'end_date', 'status', 'trigger_type']
