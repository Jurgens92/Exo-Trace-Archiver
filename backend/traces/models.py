"""
Models for storing Microsoft 365 Exchange Online message trace logs.

These models store:
1. MessageTraceLog - Individual message trace records from Exchange Online
2. PullHistory - Log of each scheduled/manual pull operation

Design Notes:
- message_id is the unique identifier from Exchange Online (MessageId field)
- raw_json stores the complete response for future reference/debugging
- event_data is a structured JSON field for parsed event details
- direction is computed from sender/recipient domain analysis
"""

from django.db import models
from django.utils import timezone


class MessageTraceLog(models.Model):
    """
    Stores individual message trace records from Exchange Online.

    Each record represents a single email's journey through Exchange Online,
    including delivery status, routing information, and event details.

    The message_id field corresponds to the MessageId from Exchange Online,
    which is the Internet Message ID (RFC 5322 Message-ID header).

    Multi-tenant: Each record is linked to a Tenant via ForeignKey.
    """

    # Link to tenant (for multi-tenant support)
    tenant = models.ForeignKey(
        'accounts.Tenant',
        on_delete=models.CASCADE,
        related_name='message_traces',
        null=True,  # Allow null for backwards compatibility during migration
        blank=True,
        help_text="The MS365 tenant this trace belongs to"
    )

    class Direction(models.TextChoices):
        INBOUND = 'Inbound', 'Inbound'
        OUTBOUND = 'Outbound', 'Outbound'
        INTERNAL = 'Internal', 'Internal'
        UNKNOWN = 'Unknown', 'Unknown'

    class Status(models.TextChoices):
        DELIVERED = 'Delivered', 'Delivered'
        FAILED = 'Failed', 'Failed'
        PENDING = 'Pending', 'Pending'
        EXPANDED = 'Expanded', 'Expanded'
        QUARANTINED = 'Quarantined', 'Quarantined'
        FILTERED = 'FilteredAsSpam', 'Filtered as Spam'
        NONE = 'None', 'None'
        UNKNOWN = 'Unknown', 'Unknown'

    # Primary identifier - Exchange Online's MessageId
    message_id = models.CharField(
        max_length=512,
        db_index=True,
        help_text="Internet Message ID from the email header (RFC 5322)"
    )

    # Message metadata
    received_date = models.DateTimeField(
        db_index=True,
        help_text="When the message was received by Exchange Online"
    )
    sender = models.EmailField(
        max_length=320,
        db_index=True,
        help_text="Sender email address"
    )
    recipient = models.EmailField(
        max_length=320,
        db_index=True,
        help_text="Recipient email address"
    )
    subject = models.CharField(
        max_length=1000,
        blank=True,
        default='',
        help_text="Email subject line"
    )

    # Delivery information
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.UNKNOWN,
        db_index=True,
        help_text="Delivery status of the message"
    )
    direction = models.CharField(
        max_length=20,
        choices=Direction.choices,
        default=Direction.UNKNOWN,
        db_index=True,
        help_text="Message direction (Inbound/Outbound/Internal)"
    )

    # Message size in bytes
    size = models.BigIntegerField(
        default=0,
        help_text="Message size in bytes"
    )

    # Structured event data (parsed from the raw response)
    # This contains additional details like transport rules, connectors, etc.
    event_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured event details and metadata"
    )

    # Archival metadata
    trace_date = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When this record was pulled from Exchange Online"
    )

    # Raw JSON response from the API (for debugging and future parsing)
    raw_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Complete raw API response for this message"
    )

    # Internal tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Message Trace Log'
        verbose_name_plural = 'Message Trace Logs'
        ordering = ['-received_date']
        # A message can appear multiple times for different recipients
        # or be re-processed, so we use a unique constraint on the combo
        indexes = [
            models.Index(fields=['tenant', 'received_date']),
            models.Index(fields=['received_date', 'sender']),
            models.Index(fields=['received_date', 'recipient']),
            models.Index(fields=['status', 'direction']),
            models.Index(fields=['trace_date']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'message_id', 'recipient', 'received_date'],
                name='unique_tenant_message_recipient_date'
            )
        ]

    def __str__(self):
        return f"{self.sender} -> {self.recipient} ({self.status}) [{self.received_date}]"

    @classmethod
    def determine_direction(cls, sender: str, recipient: str, org_domains: list[str]) -> str:
        """
        Determine message direction based on sender/recipient domains.

        Args:
            sender: Sender email address
            recipient: Recipient email address
            org_domains: List of organization's email domains

        Returns:
            Direction string (Inbound, Outbound, Internal, Unknown)
        """
        sender_domain = sender.split('@')[-1].lower() if '@' in sender else ''
        recipient_domain = recipient.split('@')[-1].lower() if '@' in recipient else ''

        org_domains_lower = [d.lower() for d in org_domains]

        sender_is_internal = sender_domain in org_domains_lower
        recipient_is_internal = recipient_domain in org_domains_lower

        if sender_is_internal and recipient_is_internal:
            return cls.Direction.INTERNAL
        elif sender_is_internal and not recipient_is_internal:
            return cls.Direction.OUTBOUND
        elif not sender_is_internal and recipient_is_internal:
            return cls.Direction.INBOUND
        else:
            return cls.Direction.UNKNOWN


class PullHistory(models.Model):
    """
    Logs each message trace pull operation (scheduled or manual).

    This provides an audit trail of when pulls occurred, how many records
    were retrieved, and any errors that happened during the pull.

    Multi-tenant: Each pull is linked to a specific Tenant.
    """

    # Link to tenant (for multi-tenant support)
    tenant = models.ForeignKey(
        'accounts.Tenant',
        on_delete=models.CASCADE,
        related_name='pull_history',
        null=True,  # Allow null for backwards compatibility during migration
        blank=True,
        help_text="The MS365 tenant this pull was for"
    )

    class Status(models.TextChoices):
        RUNNING = 'Running', 'Running'
        SUCCESS = 'Success', 'Success'
        PARTIAL = 'Partial', 'Partial Success'
        FAILED = 'Failed', 'Failed'
        CANCELLED = 'Cancelled', 'Cancelled'

    class TriggerType(models.TextChoices):
        SCHEDULED = 'Scheduled', 'Scheduled'
        MANUAL = 'Manual', 'Manual'

    # Timing
    start_time = models.DateTimeField(
        default=timezone.now,
        help_text="When the pull operation started"
    )
    end_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the pull operation completed"
    )

    # Date range that was pulled
    pull_start_date = models.DateTimeField(
        help_text="Start of the date range being pulled"
    )
    pull_end_date = models.DateTimeField(
        help_text="End of the date range being pulled"
    )

    # Results
    records_pulled = models.IntegerField(
        default=0,
        help_text="Total number of records retrieved"
    )
    records_new = models.IntegerField(
        default=0,
        help_text="Number of new records (not previously in database)"
    )
    records_updated = models.IntegerField(
        default=0,
        help_text="Number of existing records that were updated"
    )

    # Status and errors
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RUNNING,
        db_index=True
    )
    error_message = models.TextField(
        blank=True,
        default='',
        help_text="Error details if the pull failed"
    )

    # Metadata
    trigger_type = models.CharField(
        max_length=20,
        choices=TriggerType.choices,
        default=TriggerType.SCHEDULED
    )
    triggered_by = models.CharField(
        max_length=150,
        blank=True,
        default='',
        help_text="Username or 'system' for scheduled pulls"
    )

    # API method used
    api_method = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text="API method used (graph, powershell, etc.)"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pull History'
        verbose_name_plural = 'Pull History'
        ordering = ['-start_time']

    def __str__(self):
        return f"Pull {self.start_time.strftime('%Y-%m-%d %H:%M')} - {self.status} ({self.records_pulled} records)"

    @property
    def duration_seconds(self) -> float | None:
        """Calculate the duration of the pull operation in seconds."""
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    def mark_complete(self, status: str, records_pulled: int = 0,
                      records_new: int = 0, records_updated: int = 0,
                      error_message: str = ''):
        """Helper method to mark a pull as complete."""
        self.end_time = timezone.now()
        self.status = status
        self.records_pulled = records_pulled
        self.records_new = records_new
        self.records_updated = records_updated
        self.error_message = error_message
        self.save()
