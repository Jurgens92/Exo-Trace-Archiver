"""
Django management command to fix direction classification issues.

Usage:
    python manage.py fix_directions
    python manage.py fix_directions --fix
    python manage.py fix_directions --fix --tenant-id 1
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from collections import Counter

from accounts.models import Tenant
from traces.models import MessageTraceLog


class Command(BaseCommand):
    help = 'Diagnose and fix message trace direction classification issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Fix directions (default: diagnostic only)',
        )
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Process only specific tenant',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Dry run - show changes without applying',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='Number of records to update per batch (default: 500)',
        )

    def handle(self, *args, **options):
        self.stdout.write()
        self.stdout.write(self.style.SUCCESS('🔍 Direction Classification Diagnostic Tool'))
        self.stdout.write()

        # Run diagnostics
        self.analyze_tenant_domains()
        self.analyze_trace_domains(tenant_id=options['tenant_id'])
        self.analyze_current_directions(tenant_id=options['tenant_id'])
        self.suggest_missing_domains(tenant_id=options['tenant_id'])

        # Fix if requested
        if options['fix']:
            self.fix_directions(
                tenant_id=options['tenant_id'],
                dry_run=options['dry_run'],
                batch_size=options['batch_size']
            )
        else:
            self.stdout.write()
            self.stdout.write('=' * 80)
            self.stdout.write(self.style.NOTICE('ℹ️  Diagnostic complete. No changes made.'))
            self.stdout.write('   Run with --fix to update directions for existing traces.')
            self.stdout.write('=' * 80)

    def analyze_tenant_domains(self):
        """Analyze tenant domain configurations."""
        self.stdout.write('=' * 80)
        self.stdout.write('TENANT DOMAIN CONFIGURATION ANALYSIS')
        self.stdout.write('=' * 80)

        tenants = Tenant.objects.all()

        if not tenants:
            self.stdout.write(self.style.ERROR('❌ No tenants found in database!'))
            return

        for tenant in tenants:
            self.stdout.write(f"\n📁 Tenant: {tenant.name} (ID: {tenant.id})")
            self.stdout.write(f"   Status: {'✅ Active' if tenant.is_active else '❌ Inactive'}")
            self.stdout.write(f"   Organization: {tenant.organization or '(not set)'}")
            self.stdout.write(f"   Domains field: {tenant.domains or '(not set)'}")

            org_domains = tenant.get_organization_domains()
            if org_domains:
                self.stdout.write(self.style.SUCCESS(f"   ✅ Configured domains: {', '.join(org_domains)}"))
            else:
                self.stdout.write(self.style.ERROR(f"   ❌ WARNING: No domains configured!"))
                self.stdout.write(f"      This will cause all traces to be marked as 'Unknown'")

    def analyze_trace_domains(self, tenant_id=None):
        """Analyze actual domains found in message traces."""
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('ACTUAL DOMAINS IN TRACES')
        self.stdout.write('=' * 80)

        traces_qs = MessageTraceLog.objects.all()
        if tenant_id:
            traces_qs = traces_qs.filter(tenant_id=tenant_id)
            tenant = Tenant.objects.get(id=tenant_id)
            self.stdout.write(f"Analyzing traces for tenant: {tenant.name}\n")

        total_traces = traces_qs.count()
        self.stdout.write(f"Total traces: {total_traces:,}")

        if total_traces == 0:
            self.stdout.write(self.style.ERROR('❌ No traces found in database!'))
            return

        # Sample traces to find domains
        self.stdout.write('\n📊 Analyzing first 1000 traces for domain patterns...')
        traces = traces_qs[:1000]

        sender_domains = Counter()
        recipient_domains = Counter()

        for trace in traces:
            if '@' in trace.sender:
                sender_domains[trace.sender.split('@')[-1].lower()] += 1
            if '@' in trace.recipient:
                recipient_domains[trace.recipient.split('@')[-1].lower()] += 1

        self.stdout.write('\n📤 Top 10 Sender Domains:')
        for domain, count in sender_domains.most_common(10):
            self.stdout.write(f"   {domain:40} ({count:,} times)")

        self.stdout.write('\n📥 Top 10 Recipient Domains:')
        for domain, count in recipient_domains.most_common(10):
            self.stdout.write(f"   {domain:40} ({count:,} times)")

    def analyze_current_directions(self, tenant_id=None):
        """Show current direction breakdown."""
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('CURRENT DIRECTION BREAKDOWN')
        self.stdout.write('=' * 80)

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
            emoji_map = {
                'Unknown': '❓',
                'Inbound': '📥',
                'Outbound': '📤',
                'Internal': '🔄',
            }
            emoji = emoji_map.get(direction, '❔')

            self.stdout.write(f"{emoji} {direction:12} {count:8,} ({percentage:5.1f}%)")

        self.stdout.write(f"\n   {'Total':12} {total:8,}")

        # Calculate unknown percentage
        unknown_count = next((item['count'] for item in direction_counts if item['direction'] == 'Unknown'), 0)
        unknown_pct = (unknown_count / total * 100) if total > 0 else 0

        if unknown_pct > 50:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️  WARNING: {unknown_pct:.1f}% of traces are marked as 'Unknown'"
            ))
            self.stdout.write('   This suggests the tenant domain configuration is incomplete.')

    def suggest_missing_domains(self, tenant_id=None):
        """Suggest domains that should be added to tenant configuration."""
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('DOMAIN CONFIGURATION SUGGESTIONS')
        self.stdout.write('=' * 80)

        if tenant_id:
            tenants = [Tenant.objects.get(id=tenant_id)]
        else:
            tenants = Tenant.objects.all()

        for tenant in tenants:
            self.stdout.write(f"\n🔍 Analyzing tenant: {tenant.name}")

            configured_domains = set(tenant.get_organization_domains())

            if not configured_domains:
                self.stdout.write(self.style.ERROR('   ❌ No domains currently configured!'))
            else:
                self.stdout.write(f"   Current domains: {', '.join(configured_domains)}")

            traces = MessageTraceLog.objects.filter(tenant=tenant)[:1000]

            if not traces:
                self.stdout.write(self.style.WARNING('   ⚠️  No traces found for this tenant'))
                continue

            # Find domains that appear frequently
            domain_counts = Counter()
            for trace in traces:
                if '@' in trace.sender:
                    domain_counts[trace.sender.split('@')[-1].lower()] += 1
                if '@' in trace.recipient:
                    domain_counts[trace.recipient.split('@')[-1].lower()] += 1

            # Find domains that appear as both sender and recipient
            missing_domains = []
            for domain, count in domain_counts.most_common(20):
                if domain not in configured_domains:
                    sender_count = sum(1 for t in traces if '@' in t.sender and t.sender.split('@')[-1].lower() == domain)
                    recipient_count = sum(1 for t in traces if '@' in t.recipient and t.recipient.split('@')[-1].lower() == domain)

                    if sender_count > 10 and recipient_count > 10:
                        missing_domains.append((domain, count, sender_count, recipient_count))

            if missing_domains:
                self.stdout.write(self.style.SUCCESS(
                    '\n   💡 Suggested domains to add (appear as both sender and recipient):'
                ))
                for domain, total, as_sender, as_recipient in missing_domains:
                    self.stdout.write(f"      • {domain}")
                    self.stdout.write(
                        f"        (appears {total} times: {as_sender} as sender, {as_recipient} as recipient)"
                    )

                suggested_domains = [d[0] for d in missing_domains]
                all_domains = list(configured_domains) + suggested_domains

                self.stdout.write(f"\n   📝 To update this tenant:")
                self.stdout.write(self.style.WARNING(
                    f"      python manage.py shell -c \"from accounts.models import Tenant; "
                    f"t = Tenant.objects.get(id={tenant.id}); "
                    f"t.domains = '{','.join(all_domains)}'; "
                    f"t.save(); "
                    f"print('Updated!')\""
                ))
            else:
                self.stdout.write(self.style.SUCCESS('   ✅ No obvious missing domains detected'))

    def fix_directions(self, tenant_id=None, dry_run=False, batch_size=500):
        """Re-calculate directions for all traces."""
        self.stdout.write('\n' + '=' * 80)
        if dry_run:
            self.stdout.write(self.style.NOTICE('DIRECTION FIX (DRY RUN - NO CHANGES)'))
        else:
            self.stdout.write(self.style.WARNING('FIXING DIRECTIONS FOR ALL TRACES'))
        self.stdout.write('=' * 80)

        traces_qs = MessageTraceLog.objects.all()
        if tenant_id:
            traces_qs = traces_qs.filter(tenant_id=tenant_id)
            tenant = Tenant.objects.get(id=tenant_id)
            self.stdout.write(f"Fixing traces for tenant: {tenant.name}\n")

        total_traces = traces_qs.count()
        self.stdout.write(f"Total traces to process: {total_traces:,}")

        if total_traces == 0:
            self.stdout.write(self.style.ERROR('❌ No traces to fix!'))
            return

        # Get tenants to process
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
            self.stdout.write(f"\n📁 Processing tenant: {tenant.name}")
            org_domains = tenant.get_organization_domains()

            if not org_domains:
                self.stdout.write(self.style.WARNING('   ⚠️  Skipping - no domains configured for this tenant'))
                continue

            self.stdout.write(f"   Using domains: {', '.join(org_domains)}")

            tenant_traces = traces_qs.filter(tenant=tenant)
            batch = []

            for i, trace in enumerate(tenant_traces.iterator(), 1):
                old_direction = trace.direction

                new_direction = MessageTraceLog.determine_direction(
                    sender=trace.sender,
                    recipient=trace.recipient,
                    org_domains=org_domains
                )

                if new_direction != old_direction:
                    trace.direction = new_direction
                    batch.append(trace)

                    # Track changes
                    change_key = f'to_{new_direction.lower()}'
                    if change_key in changes:
                        changes[change_key] += 1
                else:
                    changes['unchanged'] += 1

                # Bulk update every batch_size records
                if len(batch) >= batch_size and not dry_run:
                    with transaction.atomic():
                        MessageTraceLog.objects.bulk_update(batch, ['direction'])
                    total_updated += len(batch)
                    self.stdout.write(
                        f"   Updated {total_updated:,} / {total_traces:,} records...",
                        ending='\r'
                    )
                    batch = []

            # Update remaining records
            if batch and not dry_run:
                with transaction.atomic():
                    MessageTraceLog.objects.bulk_update(batch, ['direction'])
                total_updated += len(batch)

        self.stdout.write()  # New line

        # Summary
        self.stdout.write('\n' + '=' * 80)
        if dry_run:
            self.stdout.write(self.style.NOTICE('SUMMARY (DRY RUN - NO CHANGES MADE)'))
        else:
            self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write('=' * 80)
        self.stdout.write(f"Total traces processed: {total_traces:,}")
        self.stdout.write(f"Total updated: {total_updated:,}")
        self.stdout.write(f"Unchanged: {changes['unchanged']:,}")
        self.stdout.write('\nDirection changes:')
        self.stdout.write(f"  → Inbound:   {changes['to_inbound']:,}")
        self.stdout.write(f"  → Outbound:  {changes['to_outbound']:,}")
        self.stdout.write(f"  → Internal:  {changes['to_internal']:,}")
        self.stdout.write(f"  → Unknown:   {changes['to_unknown']:,}")

        if not dry_run:
            self.stdout.write(self.style.SUCCESS('\n✅ Directions updated successfully!'))
