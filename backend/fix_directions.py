#!/usr/bin/env python3
"""
Diagnostic and fix script for direction classification issues.

This script:
1. Shows current tenant domain configuration
2. Analyzes actual domains found in traces
3. Suggests missing domains
4. Re-calculates directions for all traces (with --fix flag)

Usage:
    # Diagnostic only (no changes)
    python fix_directions.py

    # Fix all directions
    python fix_directions.py --fix

    # Fix for specific tenant
    python fix_directions.py --fix --tenant-id 1
"""

import os
import sys
import django
from collections import Counter

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'exo_trace_archiver.settings')
django.setup()

from django.db import transaction
from django.db.models import Count
from accounts.models import Tenant
from traces.models import MessageTraceLog


def analyze_tenant_domains():
    """Analyze tenant domain configurations."""
    print("=" * 80)
    print("TENANT DOMAIN CONFIGURATION ANALYSIS")
    print("=" * 80)

    tenants = Tenant.objects.all()

    if not tenants:
        print("❌ No tenants found in database!")
        return None

    for tenant in tenants:
        print(f"\n📁 Tenant: {tenant.name} (ID: {tenant.id})")
        print(f"   Status: {'✅ Active' if tenant.is_active else '❌ Inactive'}")
        print(f"   Organization: {tenant.organization or '(not set)'}")
        print(f"   Domains field: {tenant.domains or '(not set)'}")

        org_domains = tenant.get_organization_domains()
        if org_domains:
            print(f"   ✅ Configured domains: {', '.join(org_domains)}")
        else:
            print(f"   ❌ WARNING: No domains configured!")
            print(f"      This will cause all traces to be marked as 'Unknown'")

    return tenants


def analyze_trace_domains(tenant_id=None):
    """Analyze actual domains found in message traces."""
    print("\n" + "=" * 80)
    print("ACTUAL DOMAINS IN TRACES")
    print("=" * 80)

    # Filter by tenant if specified
    traces_qs = MessageTraceLog.objects.all()
    if tenant_id:
        traces_qs = traces_qs.filter(tenant_id=tenant_id)
        tenant = Tenant.objects.get(id=tenant_id)
        print(f"Analyzing traces for tenant: {tenant.name}\n")
    else:
        print("Analyzing traces across all tenants\n")

    total_traces = traces_qs.count()
    print(f"Total traces: {total_traces:,}")

    if total_traces == 0:
        print("❌ No traces found in database!")
        return None

    # Sample traces to find domains
    print("\n📊 Analyzing first 1000 traces for domain patterns...")
    traces = traces_qs[:1000]

    sender_domains = Counter()
    recipient_domains = Counter()
    all_domains = Counter()

    for trace in traces:
        if '@' in trace.sender:
            sender_domain = trace.sender.split('@')[-1].lower()
            sender_domains[sender_domain] += 1
            all_domains[sender_domain] += 1

        if '@' in trace.recipient:
            recipient_domain = trace.recipient.split('@')[-1].lower()
            recipient_domains[recipient_domain] += 1
            all_domains[recipient_domain] += 1

    print(f"\n📤 Top 10 Sender Domains:")
    for domain, count in sender_domains.most_common(10):
        print(f"   {domain:40} ({count:,} times)")

    print(f"\n📥 Top 10 Recipient Domains:")
    for domain, count in recipient_domains.most_common(10):
        print(f"   {domain:40} ({count:,} times)")

    return all_domains, sender_domains, recipient_domains


def analyze_current_directions(tenant_id=None):
    """Show current direction breakdown."""
    print("\n" + "=" * 80)
    print("CURRENT DIRECTION BREAKDOWN")
    print("=" * 80)

    traces_qs = MessageTraceLog.objects.all()
    if tenant_id:
        traces_qs = traces_qs.filter(tenant_id=tenant_id)

    direction_counts = traces_qs.values('direction').annotate(count=Count('id')).order_by('-count')

    total = traces_qs.count()

    for item in direction_counts:
        direction = item['direction']
        count = item['count']
        percentage = (count / total * 100) if total > 0 else 0

        # Use emoji indicators
        if direction == 'Unknown':
            emoji = '❓'
        elif direction == 'Inbound':
            emoji = '📥'
        elif direction == 'Outbound':
            emoji = '📤'
        elif direction == 'Internal':
            emoji = '🔄'
        else:
            emoji = '❔'

        print(f"{emoji} {direction:12} {count:8,} ({percentage:5.1f}%)")

    print(f"\n   {'Total':12} {total:8,}")

    # Calculate unknown percentage
    unknown_count = next((item['count'] for item in direction_counts if item['direction'] == 'Unknown'), 0)
    unknown_pct = (unknown_count / total * 100) if total > 0 else 0

    if unknown_pct > 50:
        print(f"\n⚠️  WARNING: {unknown_pct:.1f}% of traces are marked as 'Unknown'")
        print(f"   This suggests the tenant domain configuration is incomplete.")

    return direction_counts


def suggest_missing_domains(tenant_id=None):
    """Suggest domains that should be added to tenant configuration."""
    print("\n" + "=" * 80)
    print("DOMAIN CONFIGURATION SUGGESTIONS")
    print("=" * 80)

    if tenant_id:
        tenants = [Tenant.objects.get(id=tenant_id)]
    else:
        tenants = Tenant.objects.all()

    for tenant in tenants:
        print(f"\n🔍 Analyzing tenant: {tenant.name}")

        # Get configured domains
        configured_domains = set(tenant.get_organization_domains())

        if not configured_domains:
            print("   ❌ No domains currently configured!")
        else:
            print(f"   Current domains: {', '.join(configured_domains)}")

        # Analyze traces for this tenant
        traces = MessageTraceLog.objects.filter(tenant=tenant)[:1000]

        if not traces:
            print("   ⚠️  No traces found for this tenant")
            continue

        # Find domains that appear frequently
        domain_counts = Counter()
        for trace in traces:
            if '@' in trace.sender:
                domain_counts[trace.sender.split('@')[-1].lower()] += 1
            if '@' in trace.recipient:
                domain_counts[trace.recipient.split('@')[-1].lower()] += 1

        # Find domains that appear frequently but aren't configured
        missing_domains = []
        for domain, count in domain_counts.most_common(20):
            if domain not in configured_domains:
                # Check if this looks like an organizational domain
                # (appears frequently in both sender and recipient)
                sender_count = sum(1 for t in traces if '@' in t.sender and t.sender.split('@')[-1].lower() == domain)
                recipient_count = sum(1 for t in traces if '@' in t.recipient and t.recipient.split('@')[-1].lower() == domain)

                # If domain appears as both sender and recipient frequently, it's likely organizational
                if sender_count > 10 and recipient_count > 10:
                    missing_domains.append((domain, count, sender_count, recipient_count))

        if missing_domains:
            print(f"\n   💡 Suggested domains to add (appear as both sender and recipient):")
            for domain, total, as_sender, as_recipient in missing_domains:
                print(f"      • {domain}")
                print(f"        (appears {total} times: {as_sender} as sender, {as_recipient} as recipient)")
        else:
            print("\n   ✅ No obvious missing domains detected")

        # Provide example command to update
        if missing_domains:
            suggested_domains = [d[0] for d in missing_domains]
            all_domains = list(configured_domains) + suggested_domains
            print(f"\n   📝 Suggested configuration:")
            print(f"      Domains: {', '.join(all_domains)}")
            print(f"\n   To update via Django admin or shell:")
            print(f"      tenant = Tenant.objects.get(id={tenant.id})")
            print(f"      tenant.domains = '{','.join(all_domains)}'")
            print(f"      tenant.save()")


def fix_directions(tenant_id=None, dry_run=False):
    """Re-calculate directions for all traces."""
    print("\n" + "=" * 80)
    if dry_run:
        print("DIRECTION FIX (DRY RUN - NO CHANGES)")
    else:
        print("FIXING DIRECTIONS FOR ALL TRACES")
    print("=" * 80)

    # Get traces to fix
    traces_qs = MessageTraceLog.objects.all()
    if tenant_id:
        traces_qs = traces_qs.filter(tenant_id=tenant_id)
        tenant = Tenant.objects.get(id=tenant_id)
        print(f"Fixing traces for tenant: {tenant.name}\n")
    else:
        print("Fixing traces across all tenants\n")

    total_traces = traces_qs.count()
    print(f"Total traces to process: {total_traces:,}")

    if total_traces == 0:
        print("❌ No traces to fix!")
        return

    if not dry_run:
        response = input(f"\n⚠️  This will update {total_traces:,} trace records. Continue? [y/N]: ")
        if response.lower() != 'y':
            print("Aborted.")
            return

    # Group traces by tenant to get org_domains once per tenant
    if tenant_id:
        tenants_to_process = [Tenant.objects.get(id=tenant_id)]
    else:
        tenant_ids = traces_qs.values_list('tenant_id', flat=True).distinct()
        tenants_to_process = Tenant.objects.filter(id__in=tenant_ids)

    total_updated = 0
    changes = {
        'to_inbound': 0,
        'to_outbound': 0,
        'to_internal': 0,
        'to_unknown': 0,
        'unchanged': 0,
    }

    for tenant in tenants_to_process:
        print(f"\n📁 Processing tenant: {tenant.name}")
        org_domains = tenant.get_organization_domains()

        if not org_domains:
            print(f"   ⚠️  Skipping - no domains configured for this tenant")
            continue

        print(f"   Using domains: {', '.join(org_domains)}")

        tenant_traces = traces_qs.filter(tenant=tenant)
        batch_size = 500
        batch = []

        for i, trace in enumerate(tenant_traces.iterator(), 1):
            old_direction = trace.direction

            # Calculate new direction
            new_direction = MessageTraceLog.determine_direction(
                sender=trace.sender,
                recipient=trace.recipient,
                org_domains=org_domains
            )

            if new_direction != old_direction:
                trace.direction = new_direction
                batch.append(trace)

                # Track changes
                if new_direction == MessageTraceLog.Direction.INBOUND:
                    changes['to_inbound'] += 1
                elif new_direction == MessageTraceLog.Direction.OUTBOUND:
                    changes['to_outbound'] += 1
                elif new_direction == MessageTraceLog.Direction.INTERNAL:
                    changes['to_internal'] += 1
                elif new_direction == MessageTraceLog.Direction.UNKNOWN:
                    changes['to_unknown'] += 1
            else:
                changes['unchanged'] += 1

            # Bulk update every batch_size records
            if len(batch) >= batch_size and not dry_run:
                with transaction.atomic():
                    MessageTraceLog.objects.bulk_update(batch, ['direction'])
                total_updated += len(batch)
                print(f"   Updated {total_updated:,} / {total_traces:,} records...", end='\r')
                batch = []

        # Update remaining records
        if batch and not dry_run:
            with transaction.atomic():
                MessageTraceLog.objects.bulk_update(batch, ['direction'])
            total_updated += len(batch)

    print()  # New line after progress

    # Summary
    print("\n" + "=" * 80)
    if dry_run:
        print("SUMMARY (DRY RUN - NO CHANGES MADE)")
    else:
        print("SUMMARY")
    print("=" * 80)
    print(f"Total traces processed: {total_traces:,}")
    print(f"Total updated: {total_updated:,}")
    print(f"Unchanged: {changes['unchanged']:,}")
    print(f"\nDirection changes:")
    print(f"  → Inbound:   {changes['to_inbound']:,}")
    print(f"  → Outbound:  {changes['to_outbound']:,}")
    print(f"  → Internal:  {changes['to_internal']:,}")
    print(f"  → Unknown:   {changes['to_unknown']:,}")

    if not dry_run:
        print("\n✅ Directions updated successfully!")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Diagnose and fix direction classification issues',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run diagnostics only
  python fix_directions.py

  # Fix directions for all traces
  python fix_directions.py --fix

  # Fix directions for specific tenant
  python fix_directions.py --fix --tenant-id 1

  # Dry run (show what would change)
  python fix_directions.py --fix --dry-run
        """
    )
    parser.add_argument('--fix', action='store_true', help='Fix directions (default: diagnostic only)')
    parser.add_argument('--tenant-id', type=int, help='Process only specific tenant')
    parser.add_argument('--dry-run', action='store_true', help='Dry run - show changes without applying')

    args = parser.parse_args()

    print()
    print("🔍 Exo-Trace-Archiver - Direction Classification Diagnostic Tool")
    print()

    # Always run diagnostics
    analyze_tenant_domains()
    analyze_trace_domains(tenant_id=args.tenant_id)
    analyze_current_directions(tenant_id=args.tenant_id)
    suggest_missing_domains(tenant_id=args.tenant_id)

    # Fix if requested
    if args.fix:
        fix_directions(tenant_id=args.tenant_id, dry_run=args.dry_run)
    else:
        print("\n" + "=" * 80)
        print("ℹ️  Diagnostic complete. No changes made.")
        print("   Run with --fix to update directions for existing traces.")
        print("=" * 80)


if __name__ == '__main__':
    main()
