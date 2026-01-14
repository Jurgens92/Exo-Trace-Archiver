"""
PDF Generation utilities for Message Trace exports.

Generates professional PDF reports for:
1. Single message trace details
2. Search results (multiple traces)
"""

import io
import json
from datetime import datetime
from typing import List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

from .models import MessageTraceLog


def format_size(size: int) -> str:
    """Format size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def format_datetime(dt) -> str:
    """Format datetime for display."""
    if dt:
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    return "N/A"


def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text to max length with ellipsis."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


class TracePDFGenerator:
    """Generate PDF reports for message traces."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Create custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceAfter=20,
            alignment=TA_CENTER,
        ))
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=12,
            spaceBefore=15,
            spaceAfter=10,
            textColor=colors.HexColor('#1a365d'),
        ))
        self.styles.add(ParagraphStyle(
            name='SmallText',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
        ))
        self.styles.add(ParagraphStyle(
            name='FieldLabel',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#4a5568'),
        ))
        self.styles.add(ParagraphStyle(
            name='FieldValue',
            parent=self.styles['Normal'],
            fontSize=10,
        ))
        self.styles.add(ParagraphStyle(
            name='MonoText',
            parent=self.styles['Normal'],
            fontSize=8,
            fontName='Courier',
        ))

    def _create_header(self, title: str, subtitle: Optional[str] = None) -> List:
        """Create PDF header elements."""
        elements = []
        elements.append(Paragraph(title, self.styles['ReportTitle']))
        if subtitle:
            elements.append(Paragraph(subtitle, self.styles['SmallText']))
        elements.append(Spacer(1, 0.3 * inch))
        return elements

    def _create_footer_text(self) -> str:
        """Create footer text with generation timestamp."""
        return f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} | Exo-Trace-Archiver"

    def _get_status_color(self, status: str) -> colors.Color:
        """Get color for status value."""
        status_colors = {
            'Delivered': colors.HexColor('#38a169'),  # Green
            'Failed': colors.HexColor('#e53e3e'),     # Red
            'Pending': colors.HexColor('#d69e2e'),    # Yellow
            'Quarantined': colors.HexColor('#dd6b20'), # Orange
            'FilteredAsSpam': colors.HexColor('#9f7aea'), # Purple
        }
        return status_colors.get(status, colors.black)

    def _get_direction_color(self, direction: str) -> colors.Color:
        """Get color for direction value."""
        direction_colors = {
            'Inbound': colors.HexColor('#3182ce'),   # Blue
            'Outbound': colors.HexColor('#38a169'),  # Green
            'Internal': colors.HexColor('#805ad5'),  # Purple
        }
        return direction_colors.get(direction, colors.black)

    def generate_trace_detail_pdf(self, trace: MessageTraceLog, tenant_name: str = None) -> bytes:
        """
        Generate a PDF report for a single message trace detail.

        Args:
            trace: MessageTraceLog instance
            tenant_name: Optional tenant name for multi-tenant context

        Returns:
            PDF file as bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch
        )

        elements = []

        # Header
        elements.extend(self._create_header(
            "Message Trace Detail Report",
            tenant_name and f"Tenant: {tenant_name}"
        ))

        # Overview Section
        elements.append(Paragraph("Overview", self.styles['SectionHeader']))

        overview_data = [
            ['Subject:', trace.subject or '(no subject)'],
            ['Status:', trace.status],
            ['Direction:', trace.direction],
            ['From:', trace.sender],
            ['To:', trace.recipient],
            ['Received:', format_datetime(trace.received_date)],
            ['Size:', format_size(trace.size)],
            ['Trace Date:', format_datetime(trace.trace_date)],
        ]

        overview_table = Table(overview_data, colWidths=[1.5 * inch, 5 * inch])
        overview_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#4a5568')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(overview_table)
        elements.append(Spacer(1, 0.2 * inch))

        # Message ID Section
        elements.append(Paragraph("Message ID", self.styles['SectionHeader']))
        elements.append(Paragraph(trace.message_id, self.styles['MonoText']))
        elements.append(Spacer(1, 0.2 * inch))

        # Event Data Section (if available)
        if trace.event_data and isinstance(trace.event_data, dict) and len(trace.event_data) > 0:
            elements.append(Paragraph("Event Data", self.styles['SectionHeader']))
            try:
                event_json = json.dumps(trace.event_data, indent=2)
                # Split into lines for better formatting
                for line in event_json.split('\n'):
                    elements.append(Paragraph(line, self.styles['MonoText']))
            except (TypeError, ValueError):
                elements.append(Paragraph(str(trace.event_data), self.styles['MonoText']))
            elements.append(Spacer(1, 0.2 * inch))

        # Raw JSON Section (if available)
        if trace.raw_json and isinstance(trace.raw_json, dict) and len(trace.raw_json) > 0:
            elements.append(PageBreak())
            elements.append(Paragraph("Raw API Response", self.styles['SectionHeader']))
            try:
                raw_json = json.dumps(trace.raw_json, indent=2)
                for line in raw_json.split('\n')[:100]:  # Limit to first 100 lines
                    elements.append(Paragraph(line, self.styles['MonoText']))
                if len(raw_json.split('\n')) > 100:
                    elements.append(Paragraph("... (truncated)", self.styles['SmallText']))
            except (TypeError, ValueError):
                elements.append(Paragraph(str(trace.raw_json), self.styles['MonoText']))

        # Footer
        elements.append(Spacer(1, 0.5 * inch))
        elements.append(Paragraph(self._create_footer_text(), self.styles['SmallText']))

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    def generate_search_results_pdf(
        self,
        traces: List[MessageTraceLog],
        filters: dict = None,
        tenant_name: str = None,
        total_count: int = None
    ) -> bytes:
        """
        Generate a PDF report for search results.

        Args:
            traces: List of MessageTraceLog instances
            filters: Dictionary of applied filters
            tenant_name: Optional tenant name for multi-tenant context
            total_count: Total number of results (for pagination info)

        Returns:
            PDF file as bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=0.5 * inch,
            leftMargin=0.5 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch
        )

        elements = []

        # Header
        elements.extend(self._create_header(
            "Message Trace Search Results",
            tenant_name and f"Tenant: {tenant_name}"
        ))

        # Filters Summary (if any)
        if filters:
            elements.append(Paragraph("Applied Filters", self.styles['SectionHeader']))
            filter_info = []
            if filters.get('search'):
                filter_info.append(f"Search: \"{filters['search']}\"")
            if filters.get('status'):
                filter_info.append(f"Status: {filters['status']}")
            if filters.get('direction'):
                filter_info.append(f"Direction: {filters['direction']}")
            if filters.get('start_date'):
                filter_info.append(f"From: {filters['start_date'][:10]}")
            if filters.get('end_date'):
                filter_info.append(f"To: {filters['end_date'][:10]}")
            if filters.get('sender'):
                filter_info.append(f"Sender: {filters['sender']}")
            if filters.get('recipient'):
                filter_info.append(f"Recipient: {filters['recipient']}")

            if filter_info:
                elements.append(Paragraph(" | ".join(filter_info), self.styles['SmallText']))
                elements.append(Spacer(1, 0.15 * inch))

        # Results count
        actual_count = len(traces)
        if total_count and total_count > actual_count:
            count_text = f"Showing {actual_count} of {total_count} total results"
        else:
            count_text = f"Total: {actual_count} results"
        elements.append(Paragraph(count_text, self.styles['FieldLabel']))
        elements.append(Spacer(1, 0.15 * inch))

        # Results Table
        if traces:
            # Table header
            table_data = [[
                'Date',
                'Sender',
                'Recipient',
                'Subject',
                'Status',
                'Direction',
                'Size'
            ]]

            # Table rows
            for trace in traces:
                table_data.append([
                    format_datetime(trace.received_date)[:16] if trace.received_date else 'N/A',
                    truncate_text(trace.sender, 35),
                    truncate_text(trace.recipient, 35),
                    truncate_text(trace.subject or '(no subject)', 40),
                    trace.status,
                    trace.direction,
                    format_size(trace.size)
                ])

            # Create table
            col_widths = [1.2 * inch, 2 * inch, 2 * inch, 2.5 * inch, 0.9 * inch, 0.9 * inch, 0.7 * inch]
            table = Table(table_data, colWidths=col_widths, repeatRows=1)

            table.setStyle(TableStyle([
                # Header style
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d3748')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

                # Body style
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                ('ALIGN', (-1, 1), (-1, -1), 'RIGHT'),  # Size column right-aligned

                # Grid
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),

                # Alternating row colors
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),

                # Padding
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),

                # Vertical alignment
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))

            elements.append(table)
        else:
            elements.append(Paragraph("No results found", self.styles['Normal']))

        # Footer
        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Paragraph(self._create_footer_text(), self.styles['SmallText']))

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()


# Singleton instance for convenience
pdf_generator = TracePDFGenerator()
