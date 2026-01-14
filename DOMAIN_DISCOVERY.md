# Automatic Domain Discovery

This feature allows you to automatically discover and configure organization domains from Microsoft 365, eliminating the need for manual configuration.

## Overview

When you add a new tenant to Exo-Trace-Archiver, the system needs to know which email domains belong to your organization for proper direction classification (Inbound/Outbound/Internal). Instead of manually entering these domains, you can now automatically discover them from Microsoft 365.

## Benefits

✅ **No Manual Configuration** - Automatically pull verified domains from Microsoft 365
✅ **Always Accurate** - Domains are fetched directly from your Microsoft 365 tenant
✅ **Saves Time** - No need to look up and type each domain
✅ **Prevents Errors** - Eliminates typos and missing domains
✅ **Multi-Domain Support** - Automatically discovers all verified domains

## Prerequisites

### 1. Azure AD Permission

Your Azure AD app registration needs the `Domain.Read.All` permission:

1. Go to [Azure Portal](https://portal.azure.com) > **App Registrations**
2. Select your app
3. Go to **API Permissions**
4. Click **Add a permission**
5. Select **Microsoft Graph** > **Application permissions**
6. Search for and add: `Domain.Read.All`
7. Click **Grant admin consent**

**Note:** This permission is **optional**. If you prefer, you can still manually configure domains. The permission only allows reading domain information, not modifying it.

### 2. Microsoft Graph API Method

Domain discovery only works with the **Microsoft Graph API** method. If your tenant is configured to use PowerShell, domain discovery won't be available (but you can still configure domains manually).

## Usage

### Option 1: Management Command (Recommended)

#### Discover domains for a specific tenant

```bash
cd backend
python manage.py discover_domains --tenant-id 1
```

#### Discover domains for all active tenants

```bash
python manage.py discover_domains --all
```

#### Preview what would be discovered (dry run)

```bash
python manage.py discover_domains --tenant-id 1 --dry-run
```

#### Overwrite existing domains

```bash
python manage.py discover_domains --tenant-id 1 --overwrite
```

By default, the command won't update tenants that already have domains configured. Use `--overwrite` to update them anyway.

### Option 2: API Endpoint

You can also trigger domain discovery via the REST API:

**Endpoint:** `POST /api/discover-domains/`

**Headers:**
```
Authorization: Token <your-token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "tenant_id": 1,
  "overwrite": false
}
```

**Success Response (200 OK):**
```json
{
  "message": "Domains discovered and updated successfully",
  "tenant_id": 1,
  "tenant_name": "Contoso",
  "old_domains": [],
  "new_domains": [
    "contoso.com",
    "contoso.onmicrosoft.com",
    "contoso.mail.onmicrosoft.com"
  ],
  "next_steps": {
    "message": "Run fix_directions to update existing traces",
    "command": "python manage.py fix_directions --fix --tenant-id 1"
  }
}
```

**Error Response - Already Configured (400):**
```json
{
  "error": "Tenant already has domains configured",
  "current_domains": ["example.com"],
  "message": "Set overwrite=true to update existing domains"
}
```

**Error Response - Missing Permission (403):**
```json
{
  "error": "Missing permissions",
  "detail": "Domain.Read.All permission required",
  "instructions": [
    "Go to Azure Portal > App Registrations",
    "Select your app (Client ID: xxx)",
    "Go to API Permissions",
    "Add 'Domain.Read.All' (Application permission)",
    "Grant admin consent"
  ],
  "note": "This permission is optional. You can manually configure domains if preferred."
}
```

### Option 3: Frontend Integration (Coming Soon)

The API endpoint is ready for frontend integration. A "Discover Domains" button can be added to the tenant management UI.

## Complete Workflow

### For New Tenants

1. **Add the tenant** in Django Admin or via API
2. **Discover domains:**
   ```bash
   python manage.py discover_domains --tenant-id <id>
   ```
3. **Verify the domains:**
   ```bash
   python manage.py shell -c "from accounts.models import Tenant; t = Tenant.objects.get(id=<id>); print(t.get_organization_domains())"
   ```
4. **Pull message traces** (directions will be automatically classified)

### For Existing Tenants with Unknown Directions

1. **Discover domains:**
   ```bash
   python manage.py discover_domains --tenant-id <id> --overwrite
   ```
2. **Fix existing traces:**
   ```bash
   python manage.py fix_directions --fix --tenant-id <id>
   ```
3. **Verify results:**
   ```bash
   python manage.py fix_directions --tenant-id <id>
   ```

## Example Session

```bash
$ python manage.py discover_domains --tenant-id 3

🔍 Domain Discovery Tool

================================================================================
Tenant: Contoso (ID: 3)
================================================================================
Current domains: (none configured)

📡 Connecting to Microsoft 365...
🔐 Authenticating...
🌐 Fetching verified domains...

✅ Discovered 3 verified domains:
   • contoso.com
   • contoso.onmicrosoft.com
   • contoso.mail.onmicrosoft.com

✅ Tenant updated successfully!

Updated:  contoso.com,contoso.onmicrosoft.com,contoso.mail.onmicrosoft.com

📋 Next Steps:
   Run this command to fix directions for existing traces:
   python manage.py fix_directions --fix --tenant-id 3

================================================================================
SUMMARY
================================================================================
Tenants processed: 1
Tenants updated:   1

✅ Domain discovery complete!

Don't forget to run fix_directions to update existing traces:
  python manage.py fix_directions --fix --tenant-id 3
```

## What Domains Are Discovered?

The discovery process fetches **all verified domains** from your Microsoft 365 tenant, including:

- **Primary domain** (e.g., `contoso.com`)
- **Initial domain** (e.g., `contoso.onmicrosoft.com`)
- **Additional verified domains** (any custom domains you've added)
- **Mail routing domains** (e.g., `contoso.mail.onmicrosoft.com`)

Only **verified** domains are included. Unverified or pending domains are excluded.

## Troubleshooting

### "Missing permissions to read domains"

**Problem:** The Azure AD app doesn't have `Domain.Read.All` permission.

**Solution:**
1. Add the permission in Azure Portal (see Prerequisites above)
2. Grant admin consent
3. Wait a few minutes for permission to propagate
4. Try again

**Alternative:** Manually configure domains instead:
```bash
python manage.py shell -c "from accounts.models import Tenant; t = Tenant.objects.get(id=3); t.domains = 'yourdomain.com,yourdomain.onmicrosoft.com'; t.save()"
```

### "Domain discovery not supported"

**Problem:** The tenant is configured to use PowerShell API method.

**Solution:** Domain discovery only works with Microsoft Graph API. Either:
1. Change the tenant's `api_method` to `graph` (if your app has Graph permissions)
2. Manually configure domains

### "No verified domains found"

**Problem:** The Microsoft 365 tenant has no verified domains.

**Solution:** This is very unusual. Verify:
1. You're connecting to the correct tenant
2. The tenant is properly set up in Microsoft 365
3. Try manually checking domains in Microsoft 365 Admin Center

### "Authentication failed"

**Problem:** Can't authenticate with Microsoft 365.

**Solution:**
1. Verify tenant credentials (Tenant ID, Client ID)
2. Check certificate/secret configuration
3. Ensure the certificate/secret hasn't expired
4. Test with a manual trace pull first

## Security Considerations

### What Permission Level is Required?

`Domain.Read.All` is an **Application** permission (not Delegated). This means:
- ✅ It only allows reading domain information
- ✅ It does not allow creating, modifying, or deleting domains
- ✅ It requires admin consent (which is appropriate for this app)
- ✅ It's read-only and low-risk

### Can I Skip This Permission?

**Yes!** The `Domain.Read.All` permission is **completely optional**. You can:
- Manually configure domains in Django Admin
- Use the `domains` field on each tenant
- Skip automatic discovery entirely

The automatic discovery is just a convenience feature.

## API Implementation Details

### Graph API Endpoint Used

```
GET https://graph.microsoft.com/v1.0/domains
```

### Response Format

```json
{
  "value": [
    {
      "id": "contoso.com",
      "authenticationType": "Managed",
      "availabilityStatus": null,
      "isAdminManaged": true,
      "isDefault": true,
      "isInitial": false,
      "isRoot": true,
      "isVerified": true,
      "supportedServices": ["Email", "OfficeCommunicationsOnline"]
    },
    {
      "id": "contoso.onmicrosoft.com",
      "isInitial": true,
      "isVerified": true
    }
  ]
}
```

### Filtering Logic

The code filters for:
```python
verified_domains = [
    domain['id']
    for domain in domains_data
    if domain.get('isVerified', False)
]
```

Only domains where `isVerified == true` are included.

## Integration with Direction Classification

Once domains are discovered and configured:

1. **New traces** pulled from Microsoft 365 are automatically classified using the domains
2. **Existing traces** need to be updated using `fix_directions --fix`
3. The classification logic compares sender/recipient domains against configured domains:
   - Internal → Internal = **Internal** 🔄
   - Internal → External = **Outbound** 📤
   - External → Internal = **Inbound** 📥
   - External → External = **Unknown** ❓

See `DIRECTION_FIX_GUIDE.md` for more details on direction classification.

## Best Practices

1. **Run domain discovery immediately after adding a tenant**
   - This ensures all future trace pulls have correct direction classification

2. **Re-run if you add new domains to Microsoft 365**
   ```bash
   python manage.py discover_domains --tenant-id <id> --overwrite
   python manage.py fix_directions --fix --tenant-id <id>
   ```

3. **Include in your tenant onboarding checklist**
   - Add tenant
   - Configure credentials
   - Discover domains ✓
   - Test manual pull
   - Verify direction classification

4. **Consider automating for multi-tenant deployments**
   ```bash
   # Discover domains for all new tenants without domains configured
   python manage.py discover_domains --all
   ```

## Future Enhancements

Potential future improvements:

- [ ] Frontend UI button for "Discover Domains"
- [ ] Automatic domain discovery when tenant is created
- [ ] Scheduled task to refresh domains periodically
- [ ] Notification when new domains are detected
- [ ] Support for custom domain filtering rules

## Related Documentation

- [DIRECTION_FIX_GUIDE.md](DIRECTION_FIX_GUIDE.md) - Fix direction classification issues
- [README.md](README.md) - Main project documentation

## Questions?

If you have questions about domain discovery:

1. Check the troubleshooting section above
2. Verify your Azure AD permissions
3. Test with `--dry-run` first
4. Check the logs for detailed error messages
