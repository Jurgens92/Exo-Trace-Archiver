# Automatic Domain Refresh

This feature automatically keeps organization domains up-to-date by refreshing them from Microsoft 365 before each trace pull.

## Overview

Instead of manually running domain discovery when you add new domains to Microsoft 365, the system now automatically:
- Checks if domains need refreshing before each pull
- Updates domains from Microsoft 365 if they're stale
- Uses configurable refresh intervals
- Falls back gracefully if discovery fails

## How It Works

### Automatic Refresh Logic

When you trigger a trace pull (manual or scheduled):

1. **Authentication** - System authenticates with Microsoft 365
2. **Domain Check** - Checks if domains need refreshing:
   - Are domains missing entirely? → **Refresh**
   - Has it been > X hours since last refresh? → **Refresh**
   - Otherwise → **Skip** (use cached domains)
3. **Pull Traces** - Proceeds with trace pull using current/updated domains

### Default Behavior

By default:
- ✅ Auto-refresh is **enabled**
- ⏰ Refresh interval is **24 hours**
- 🔄 Runs automatically before each pull
- ⚠️ Continues with old domains if refresh fails

## Configuration

All settings are configurable via the UI or API.

### Via API

**Get Current Settings:**
```bash
GET /api/accounts/settings/
```

**Update Settings:**
```bash
PATCH /api/accounts/settings/
Content-Type: application/json

{
  "domain_discovery_auto_refresh": true,
  "domain_discovery_refresh_hours": 24
}
```

### Via Frontend (Settings Page)

Navigate to **Settings** and configure:

**Domain Discovery Settings:**
- **Auto-Refresh Domains**: Enable/disable automatic refresh
- **Refresh Interval**: How often to refresh (1-168 hours)

**Scheduled Pull Settings:**
- **Enable Scheduled Pulls**: Turn automated pulls on/off
- **Pull Schedule**: Configure time of day (hour and minute, UTC)

## Settings Reference

### Domain Discovery Settings

| Setting | Type | Default | Range | Description |
|---------|------|---------|-------|-------------|
| `domain_discovery_auto_refresh` | Boolean | `true` | - | Enable automatic domain refresh before pulls |
| `domain_discovery_refresh_hours` | Integer | `24` | 1-168 | Hours between domain refreshes |

### Scheduled Pull Settings

| Setting | Type | Default | Range | Description |
|---------|------|---------|-------|-------------|
| `scheduled_pull_enabled` | Boolean | `true` | - | Enable automated daily pulls |
| `scheduled_pull_hour` | Integer | `1` | 0-23 | Hour to run pulls (UTC) |
| `scheduled_pull_minute` | Integer | `0` | 0-59 | Minute to run pulls |

## Usage Examples

### Scenario 1: New Tenant Added

```
1. Add new tenant in Django Admin
2. Trigger first manual pull
   → Auto-discovers domains (no domains configured yet)
   → Saves domains to database
   → Pulls traces with correct classification
3. Done! No manual domain configuration needed
```

### Scenario 2: Add New Domain to M365

```
1. Add newdomain.com to Microsoft 365
2. Wait up to 24 hours (or change refresh interval to 1 hour)
3. Next scheduled pull automatically picks up new domain
4. All future traces correctly classified
```

### Scenario 3: Manual Domain Refresh

Want to force immediate refresh without waiting?

```bash
# Option 1: Lower the refresh interval temporarily
PATCH /api/accounts/settings/
{"domain_discovery_refresh_hours": 1}

# Option 2: Run discover_domains command manually
python manage.py discover_domains --tenant-id 3 --overwrite
```

## Refresh Intervals Guide

Choose the right interval for your needs:

| Interval | Use Case | Pros | Cons |
|----------|----------|------|------|
| **1 hour** | Rapidly changing domains | Always current | Extra API calls |
| **6 hours** | Active development | Good balance | Some delay |
| **24 hours** ⭐ | Production (default) | Minimal overhead | 24h delay |
| **168 hours** (1 week) | Stable environments | Least API calls | Week delay |

**Recommendation:** Use **24 hours** for most production environments.

## How Domains Are Tracked

Each tenant now has:
- `domains` field - Comma-separated list of domains
- `domains_last_updated` field - Timestamp of last refresh

Example:
```python
tenant = Tenant.objects.get(id=3)
print(tenant.domains)  # "itwindow.co.za,itwindowcc.onmicrosoft.com"
print(tenant.domains_last_updated)  # 2026-01-14 15:30:00+00:00
```

## Logging

Auto-refresh events are logged for monitoring:

```
INFO: Auto-refreshing domains for tenant IT Window: No domains configured
INFO: Domains updated for tenant IT Window: Old: (none), New: itwindow.co.za,itwindowcc.onmicrosoft.com
INFO: Domain auto-refresh: Domains refreshed: 2 domains found
```

If refresh fails:
```
WARNING: Auto-discovery failed for tenant IT Window: Insufficient permissions. Continuing with existing domains...
```

## Fallback Behavior

If auto-refresh fails:
- ✅ Continues with existing domains (doesn't block the pull)
- ⚠️ Logs warning for investigation
- 🔄 Will retry on next pull

This ensures pulls never fail due to domain discovery issues.

## Requirements

For automatic refresh to work:

1. **Microsoft Graph API** - Tenant must use Graph API (not PowerShell)
2. **Domain.Read.All Permission** - Azure AD app must have this permission
3. **Auto-refresh Enabled** - Setting must be `true` (default)

If any requirement is missing:
- Auto-refresh is skipped
- Manual domain configuration is required
- Trace pulls continue normally

## Disabling Auto-Refresh

To disable automatic refresh:

```bash
PATCH /api/accounts/settings/
{
  "domain_discovery_auto_refresh": false
}
```

When disabled:
- Domains are never auto-refreshed
- You must manually run `discover_domains` when adding domains
- Reduces API calls to Microsoft 365

## API Endpoints

### Get Settings
```http
GET /api/accounts/settings/
Authorization: Token <your-token>
```

**Response:**
```json
{
  "domain_discovery_auto_refresh": true,
  "domain_discovery_refresh_hours": 24,
  "scheduled_pull_enabled": true,
  "scheduled_pull_hour": 1,
  "scheduled_pull_minute": 0,
  "updated_at": "2026-01-14T15:30:00Z",
  "updated_by_username": "admin"
}
```

### Update Settings
```http
PATCH /api/accounts/settings/
Authorization: Token <your-token>
Content-Type: application/json

{
  "domain_discovery_auto_refresh": true,
  "domain_discovery_refresh_hours": 6
}
```

**Response:**
```json
{
  "message": "Settings updated successfully",
  "settings": {
    "domain_discovery_auto_refresh": true,
    "domain_discovery_refresh_hours": 6,
    ...
  }
}
```

## Migration Notes

### Upgrading from Previous Versions

When upgrading:

1. **Run Migrations:**
   ```bash
   python manage.py migrate accounts
   ```

2. **Initialize Settings:**
   Settings are automatically created with defaults on first access.

3. **Update Existing Tenants:**
   ```bash
   # Discover domains for all existing tenants
   python manage.py discover_domains --all
   ```

### Database Changes

Two new fields added:
- `Tenant.domains_last_updated` - Tracks refresh timestamp
- `AppSettings` model - Stores application-wide settings

## Troubleshooting

### "Domains never refresh"

**Check:**
1. Is auto-refresh enabled? `GET /api/accounts/settings/`
2. Has enough time passed? Check refresh interval
3. Check logs for errors
4. Verify Domain.Read.All permission in Azure AD

**Solution:**
```bash
# Force immediate refresh
python manage.py discover_domains --tenant-id <id> --overwrite
```

### "Too many API calls to Microsoft"

**Problem:** Refresh interval too short

**Solution:**
```bash
# Increase interval to 24 hours
PATCH /api/accounts/settings/
{"domain_discovery_refresh_hours": 24}
```

### "Some domains still missing"

**Check:**
1. Are all domains verified in Microsoft 365?
2. Check tenant's current domains: `GET /api/accounts/tenants/<id>/`
3. Manually verify: `python manage.py discover_domains --tenant-id <id> --dry-run`

**Solution:**
```bash
# Re-discover domains
python manage.py discover_domains --tenant-id <id> --overwrite
```

## Best Practices

1. **Use Default Settings** - 24-hour refresh works for most cases
2. **Monitor Logs** - Check for auto-refresh warnings
3. **Verify After M365 Changes** - After adding domains, check they were discovered
4. **Don't Disable Unless Needed** - Auto-refresh is low-overhead
5. **Set Appropriate Intervals** - Match your domain change frequency

## Performance Impact

Auto-refresh adds minimal overhead:

- **API Calls:** 1 extra call per pull (only when refresh needed)
- **Database:** 1 UPDATE query per tenant (only when domains change)
- **Time:** < 1 second typically

For a tenant with 24-hour refresh:
- 1 domain API call per day
- Negligible impact on pull performance

## Security Considerations

- **Domain.Read.All** is read-only, low-risk permission
- No data is modified in Microsoft 365
- Only verified domains are used
- Settings require admin authentication

## Related Documentation

- [DOMAIN_DISCOVERY.md](DOMAIN_DISCOVERY.md) - Manual domain discovery
- [DIRECTION_FIX_GUIDE.md](DIRECTION_FIX_GUIDE.md) - Direction classification
- [README.md](README.md) - Main documentation

## Questions?

Common questions:

**Q: Will this break my existing setup?**
A: No. Auto-refresh uses existing domains if refresh fails. Fully backward compatible.

**Q: Can I still manually configure domains?**
A: Yes. Manual configuration always works and takes precedence.

**Q: What if I don't have Domain.Read.All permission?**
A: Auto-refresh is skipped. Use manual domain configuration instead.

**Q: Does this work with PowerShell API method?**
A: No. Only Microsoft Graph API supports domain discovery. PowerShell tenants require manual configuration.

**Q: Can I configure different intervals per tenant?**
A: Currently, the interval is global. All tenants use the same setting.
