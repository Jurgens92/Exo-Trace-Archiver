"""
Data migration to switch tenants using PowerShell API method to Graph API
on systems where PowerShell is not installed.
"""
import shutil

from django.db import migrations


def switch_powershell_to_graph(apps, schema_editor):
    """Switch PowerShell tenants to Graph API if PowerShell is not available."""
    if shutil.which('pwsh') or shutil.which('powershell'):
        return  # PowerShell is installed, no changes needed

    Tenant = apps.get_model('accounts', 'Tenant')
    updated = Tenant.objects.filter(api_method='powershell').update(api_method='graph')
    if updated:
        print(f"\n  Switched {updated} tenant(s) from PowerShell to Graph API "
              f"(PowerShell not installed on this system)")


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_tenantauditlog'),
    ]

    operations = [
        migrations.RunPython(
            switch_powershell_to_graph,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
