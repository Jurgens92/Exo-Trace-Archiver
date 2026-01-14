# Direction Classification Fix Guide

## Problem

Message traces are being classified as "Unknown" direction instead of "Inbound", "Outbound", or "Internal".

## Root Cause

The direction classification depends on the **organization domains** configured for each tenant. If these domains are not properly configured, traces cannot be correctly classified.

### How Direction Classification Works

The system classifies message directions by comparing sender and recipient email domains against your organization's configured domains:

| Sender Domain | Recipient Domain | Direction |
|---------------|------------------|-----------|
| Internal      | Internal         | **Internal** 🔄 |
| Internal      | External         | **Outbound** 📤 |
| External      | Internal         | **Inbound** 📥 |
| External      | External         | **Unknown** ❓ |

**If no domains are configured, ALL traces will be marked as "Unknown"** because the system can't determine what's internal vs external.

## Solution

### Step 1: Run the Diagnostic Tool

First, let's diagnose the issue:

```bash
# Navigate to backend directory
cd backend

# Run diagnostic (no changes will be made)
python fix_directions.py

# OR use Django management command
python manage.py fix_directions
```

This will show you:
1. Current tenant domain configuration
2. Actual domains found in your traces
3. Current direction breakdown
4. Suggested domains to add

### Step 2: Configure Tenant Domains

Based on the diagnostic output, you need to configure your tenant's domains.

#### Option A: Via Django Admin

1. Log into Django Admin: `http://your-server:8000/admin/`
2. Navigate to **Accounts** → **Tenants**
3. Click on your tenant
4. Fill in the **Domains** field with a comma-separated list of your organization's email domains

Example:
```
contoso.com,contoso.onmicrosoft.com,contoso.mail.onmicrosoft.com
```

#### Option B: Via Django Shell

```bash
python manage.py shell
```

```python
from accounts.models import Tenant

# Get your tenant
tenant = Tenant.objects.get(id=1)  # Replace 1 with your tenant ID

# Set domains (comma-separated, no spaces)
tenant.domains = 'contoso.com,contoso.onmicrosoft.com,contoso.mail.onmicrosoft.com'

# Save
tenant.save()

print(f"Updated! Configured domains: {tenant.get_organization_domains()}")
```

#### Option C: Quick Shell Command

```bash
python manage.py shell -c "from accounts.models import Tenant; t = Tenant.objects.get(id=1); t.domains = 'yourdomain.com,yourdomain.onmicrosoft.com'; t.save(); print('Updated!')"
```

### Step 3: Fix Existing Traces

After configuring the domains, re-calculate directions for existing traces:

```bash
# Preview changes (dry run)
python fix_directions.py --fix --dry-run

# Apply the fix
python fix_directions.py --fix

# OR using Django management command
python manage.py fix_directions --fix
```

For a specific tenant only:
```bash
python fix_directions.py --fix --tenant-id 1
```

### Step 4: Verify

Run the diagnostic again to verify:
```bash
python fix_directions.py
```

You should now see a proper breakdown like:
```
📥 Inbound       1,234 (40.0%)
📤 Outbound        892 (28.8%)
🔄 Internal        969 (31.2%)
❓ Unknown           0 (0.0%)
```

## Common Scenarios

### Scenario 1: Single Organization Domain

If your organization uses a single domain (e.g., `contoso.com`):

```python
tenant.domains = 'contoso.com'
```

### Scenario 2: Multiple Domains

If you have multiple domains (common in Microsoft 365):

```python
# Include all domains your organization uses:
# - Your primary domain
# - Your onmicrosoft.com domain
# - Any additional verified domains
tenant.domains = 'contoso.com,contoso.onmicrosoft.com,contoso.mail.onmicrosoft.com'
```

### Scenario 3: After Domain Migration

If your organization recently changed domains:

```python
# Include both old and new domains during transition period
tenant.domains = 'oldcompany.com,newcompany.com,contoso.onmicrosoft.com'
```

## Preventing Future Issues

### For New Traces

Once you configure the domains, **all new traces will be classified correctly automatically**. No additional action needed.

### For Existing Traces

You need to run the fix script once to update historical data:
```bash
python manage.py fix_directions --fix
```

### Regular Maintenance

If you add new domains to your organization:
1. Update the tenant's `domains` field
2. Run the fix script to update existing traces:
   ```bash
   python manage.py fix_directions --fix
   ```

## Troubleshooting

### Issue: Still seeing many "Unknown" after fix

**Cause**: The domains might not be configured correctly, or there are legitimate external-to-external traces.

**Solution**:
1. Run diagnostic: `python manage.py fix_directions`
2. Check "Domain Configuration Suggestions" section
3. Look at the "Top Sender/Recipient Domains" - are your organization domains there?
4. Update tenant domains to include all organizational domains
5. Run fix again

### Issue: Traces marked as "Internal" that should be "Inbound"

**Cause**: You may have included external domains in your organization domains list.

**Solution**:
1. Review your tenant's `domains` field
2. Remove any external domains
3. Only include domains that belong to your organization
4. Run fix: `python manage.py fix_directions --fix`

### Issue: Getting "No domains configured" warning

**Cause**: Both the `domains` and `organization` fields are empty.

**Solution**:
1. Set the `domains` field with your organization's email domains
2. If you're unsure, run the diagnostic first - it will suggest domains

## API Integration

The direction is automatically calculated when traces are pulled from Microsoft 365. The logic is in:
- `backend/traces/models.py` - `MessageTraceLog.determine_direction()`
- `backend/traces/tasks.py` - `_store_traces_for_tenant()`

## Database Schema

The `Tenant` model has two fields for domains:

1. **`domains`** (TextField) - **Preferred**
   - Comma-separated list of organizational email domains
   - Example: `"contoso.com,contoso.onmicrosoft.com"`
   - Used first by `get_organization_domains()`

2. **`organization`** (CharField) - **Fallback**
   - Single organization name
   - Example: `"contoso.onmicrosoft.com"`
   - Used only if `domains` is empty

**Best Practice**: Always use the `domains` field for explicit control.

## Need Help?

If you're still experiencing issues:

1. Run the diagnostic and save the output:
   ```bash
   python manage.py fix_directions > diagnostic_output.txt
   ```

2. Check the output for warnings and suggestions

3. Verify your tenant configuration:
   ```bash
   python manage.py shell -c "from accounts.models import Tenant; [print(f'{t.name}: {t.get_organization_domains()}') for t in Tenant.objects.all()]"
   ```

## Summary Commands

```bash
# Quick diagnostic
python manage.py fix_directions

# Fix all traces
python manage.py fix_directions --fix

# Fix specific tenant
python manage.py fix_directions --fix --tenant-id 1

# Preview changes without applying
python manage.py fix_directions --fix --dry-run

# Configure tenant domains (replace values)
python manage.py shell -c "from accounts.models import Tenant; t = Tenant.objects.get(id=1); t.domains = 'yourdomain.com,yourdomain.onmicrosoft.com'; t.save(); print('Updated to:', t.get_organization_domains())"
```
