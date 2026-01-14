"""
Django management command to auto-discover organization domains from Microsoft 365.

This command uses the Microsoft Graph API to fetch all verified domains for a tenant
and automatically updates the tenant's 'domains' field for direction classification.

Usage:
    python manage.py discover_domains --tenant-id 1
    python manage.py discover_domains --all
    python manage.py discover_domains --tenant-id 1 --dry-run
"""

from django.core.management.base import BaseCommand, CommandError

from accounts.models import Tenant
from traces.ms365_client import (
    get_ms365_client_for_tenant,
    MS365AuthenticationError,
    MS365APIError,
)


class Command(BaseCommand):
    help = 'Auto-discover organization domains from Microsoft 365 for direction classification'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Specific tenant ID to discover domains for',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Discover domains for all active tenants',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing domains (default: only update if empty)',
        )

    def handle(self, *args, **options):
        self.stdout.write()
        self.stdout.write(self.style.SUCCESS('🔍 Domain Discovery Tool'))
        self.stdout.write()

        # Determine which tenants to process
        if options['tenant_id']:
            try:
                tenants = [Tenant.objects.get(id=options['tenant_id'])]
            except Tenant.DoesNotExist:
                raise CommandError(f"Tenant with ID {options['tenant_id']} not found")
        elif options['all']:
            tenants = Tenant.objects.filter(is_active=True)
            if not tenants:
                self.stdout.write(self.style.WARNING('No active tenants found'))
                return
        else:
            raise CommandError(
                'Please specify either --tenant-id <id> or --all'
            )

        dry_run = options['dry_run']
        overwrite = options['overwrite']

        if dry_run:
            self.stdout.write(self.style.NOTICE('🔍 DRY RUN MODE - No changes will be made'))
            self.stdout.write()

        # Process each tenant
        total_processed = 0
        total_updated = 0
        total_errors = 0

        for tenant in tenants:
            total_processed += 1
            self.stdout.write('=' * 80)
            self.stdout.write(f'Tenant: {tenant.name} (ID: {tenant.id})')
            self.stdout.write('=' * 80)

            # Show current configuration
            current_domains = tenant.get_organization_domains()
            if current_domains:
                self.stdout.write(f'Current domains: {", ".join(current_domains)}')
            else:
                self.stdout.write(self.style.WARNING('Current domains: (none configured)'))

            # Check if we should skip
            if current_domains and not overwrite:
                self.stdout.write(
                    self.style.NOTICE(
                        '⏭️  Skipping - domains already configured. Use --overwrite to update.'
                    )
                )
                self.stdout.write()
                continue

            try:
                # Get client for this tenant
                self.stdout.write(f'\n📡 Connecting to Microsoft 365...')
                client = get_ms365_client_for_tenant(tenant)

                # Check if client supports domain discovery (Graph API only)
                if not hasattr(client, 'get_verified_domains'):
                    self.stdout.write(
                        self.style.WARNING(
                            '⚠️  Domain discovery not supported for this tenant\'s API method. '
                            'Only Microsoft Graph API supports automatic domain discovery.'
                        )
                    )
                    self.stdout.write()
                    continue

                # Authenticate
                self.stdout.write('🔐 Authenticating...')
                client.authenticate()

                # Fetch domains
                self.stdout.write('🌐 Fetching verified domains...')
                discovered_domains = client.get_verified_domains()

                if not discovered_domains:
                    self.stdout.write(self.style.WARNING('⚠️  No verified domains found'))
                    self.stdout.write()
                    continue

                # Display discovered domains
                self.stdout.write(
                    self.style.SUCCESS(f'\n✅ Discovered {len(discovered_domains)} verified domains:')
                )
                for domain in discovered_domains:
                    self.stdout.write(f'   • {domain}')

                # Update tenant (if not dry run)
                if not dry_run:
                    old_domains = tenant.domains
                    tenant.domains = ','.join(discovered_domains)
                    tenant.save()

                    self.stdout.write()
                    self.stdout.write(self.style.SUCCESS('✅ Tenant updated successfully!'))

                    # Show what changed
                    if old_domains:
                        self.stdout.write(f'\nPrevious: {old_domains}')
                    self.stdout.write(f'Updated:  {tenant.domains}')

                    total_updated += 1
                else:
                    self.stdout.write()
                    self.stdout.write(self.style.NOTICE('💡 Would update tenant with:'))
                    self.stdout.write(f'   domains = "{",".join(discovered_domains)}"')

                # Suggest next steps
                if not dry_run:
                    self.stdout.write()
                    self.stdout.write(self.style.WARNING('📋 Next Steps:'))
                    self.stdout.write(
                        '   Run this command to fix directions for existing traces:'
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'   python manage.py fix_directions --fix --tenant-id {tenant.id}'
                        )
                    )

            except MS365AuthenticationError as e:
                total_errors += 1
                self.stdout.write()
                self.stdout.write(
                    self.style.ERROR(f'❌ Authentication failed: {str(e)}')
                )
                self.stdout.write()
                self.stdout.write('💡 Troubleshooting:')
                self.stdout.write('   1. Verify tenant credentials (Client ID, Tenant ID)')
                self.stdout.write('   2. Check certificate/secret configuration')
                self.stdout.write('   3. Ensure Azure AD app has correct permissions')

            except MS365APIError as e:
                total_errors += 1
                error_msg = str(e)
                self.stdout.write()

                # Check if it's a permissions error
                if 'Domain.Read.All' in error_msg or 'Insufficient permissions' in error_msg:
                    self.stdout.write(
                        self.style.ERROR(
                            '❌ Missing permissions to read domains'
                        )
                    )
                    self.stdout.write()
                    self.stdout.write('💡 To enable automatic domain discovery:')
                    self.stdout.write('   1. Go to Azure Portal > App Registrations')
                    self.stdout.write(f'   2. Select your app (Client ID: {tenant.client_id})')
                    self.stdout.write('   3. Go to API Permissions')
                    self.stdout.write('   4. Add "Domain.Read.All" (Application permission)')
                    self.stdout.write('   5. Grant admin consent')
                    self.stdout.write()
                    self.stdout.write(
                        '   Note: This permission is optional. You can manually '
                        'configure domains if preferred.'
                    )
                else:
                    self.stdout.write(self.style.ERROR(f'❌ API error: {error_msg}'))

            except Exception as e:
                total_errors += 1
                self.stdout.write()
                self.stdout.write(
                    self.style.ERROR(f'❌ Unexpected error: {str(e)}')
                )

            self.stdout.write()

        # Summary
        self.stdout.write('=' * 80)
        if dry_run:
            self.stdout.write(self.style.NOTICE('SUMMARY (DRY RUN)'))
        else:
            self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'Tenants processed: {total_processed}')

        if not dry_run:
            self.stdout.write(f'Tenants updated:   {total_updated}')

        if total_errors > 0:
            self.stdout.write(
                self.style.ERROR(f'Errors:            {total_errors}')
            )

        self.stdout.write()

        if dry_run and total_processed > 0:
            self.stdout.write(
                self.style.NOTICE('Run without --dry-run to apply changes')
            )

        # Final message
        if not dry_run and total_updated > 0:
            self.stdout.write()
            self.stdout.write(self.style.SUCCESS('✅ Domain discovery complete!'))
            self.stdout.write()
            self.stdout.write('Don\'t forget to run fix_directions to update existing traces:')
            if options['tenant_id']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  python manage.py fix_directions --fix --tenant-id {options["tenant_id"]}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('  python manage.py fix_directions --fix')
                )
