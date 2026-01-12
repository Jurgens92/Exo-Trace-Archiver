"""
Microsoft 365 / Exchange Online client for retrieving message traces.

This module provides two methods for retrieving message trace data:

1. Microsoft Graph API (Preferred - Public Preview as of Jan 2026)
   - Uses the Reports.Read.All application permission
   - REST API calls with MSAL authentication
   - Recommended for new implementations

2. Exchange Online PowerShell (Fallback)
   - Uses Exchange.ManageAsApp application permission
   - Calls PowerShell via subprocess
   - Required: ExchangeOnlineManagement module installed
   - Uses Get-MessageTraceV2 cmdlet (replaces legacy Get-MessageTrace)

Authentication Methods:
- Certificate-based (recommended for unattended/service scenarios)
- Client secret (simpler but less secure)

Important Notes:
- Exchange Online retains message traces for only 10 days
- Legacy Reporting Web Service deprecated ~March 18, 2026
- Get-MessageTraceV2 is the recommended PowerShell cmdlet
- Graph API Message Trace is in public preview (Jan 2026)
"""

import json
import logging
import subprocess
import tempfile
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any
from pathlib import Path

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('traces')


class MS365AuthenticationError(Exception):
    """Raised when authentication with Microsoft 365 fails."""
    pass


class MS365APIError(Exception):
    """Raised when API calls to Microsoft 365 fail."""
    pass


class BaseMS365Client(ABC):
    """
    Abstract base class for Microsoft 365 clients.

    Subclasses implement specific authentication and API methods.
    """

    def __init__(self):
        self.tenant_id = settings.MS365_TENANT_ID
        self.client_id = settings.MS365_CLIENT_ID
        self._validate_config()

    def _validate_config(self):
        """Validate that required configuration is present."""
        if not self.tenant_id:
            raise MS365AuthenticationError(
                "MS365_TENANT_ID not configured. "
                "Please set it in your .env file."
            )
        if not self.client_id:
            raise MS365AuthenticationError(
                "MS365_CLIENT_ID not configured. "
                "Please set it in your .env file."
            )

    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with Microsoft 365. Returns True on success."""
        pass

    @abstractmethod
    def get_message_traces(
        self,
        start_date: datetime,
        end_date: datetime,
        page_size: int = 1000
    ) -> list[dict[str, Any]]:
        """
        Retrieve message traces for the specified date range.

        Args:
            start_date: Start of the date range (UTC)
            end_date: End of the date range (UTC)
            page_size: Number of records per page

        Returns:
            List of message trace records as dictionaries
        """
        pass


class GraphAPIClient(BaseMS365Client):
    """
    Microsoft Graph API client for retrieving message traces.

    This uses the Reports API endpoint for message traces, which is
    in public preview as of January 2026.

    Required Permission: Reports.Read.All (Application)

    Graph API is preferred over PowerShell because:
    - Native REST API (no external dependencies)
    - Better performance and scalability
    - More consistent authentication flow
    - Better error handling and pagination
    """

    # Graph API endpoints
    # Note: As of Jan 2026, message trace is in preview
    # The exact endpoint may change - check Microsoft docs
    GRAPH_URL = "https://graph.microsoft.com/v1.0"
    GRAPH_BETA_URL = "https://graph.microsoft.com/beta"

    # Message trace endpoint (beta as of Jan 2026)
    # This may move to v1.0 in the future
    MESSAGE_TRACE_ENDPOINT = "/reports/getEmailActivityUserDetail"

    def __init__(self):
        super().__init__()
        self._access_token = None
        self._token_expiry = None

    def authenticate(self) -> bool:
        """
        Authenticate using MSAL (Microsoft Authentication Library).

        Supports both certificate and client secret authentication.
        """
        try:
            import msal
        except ImportError:
            raise MS365AuthenticationError(
                "MSAL library not installed. "
                "Install it with: pip install msal"
            )

        auth_method = settings.MS365_AUTH_METHOD

        if auth_method == 'certificate':
            return self._authenticate_with_certificate(msal)
        else:
            return self._authenticate_with_secret(msal)

    def _authenticate_with_certificate(self, msal) -> bool:
        """Authenticate using certificate-based credentials."""
        cert_path = settings.MS365_CERTIFICATE_PATH
        cert_password = settings.MS365_CERTIFICATE_PASSWORD

        if not cert_path:
            raise MS365AuthenticationError(
                "MS365_CERTIFICATE_PATH not configured for certificate auth"
            )

        # Read certificate
        cert_path = Path(cert_path)
        if not cert_path.exists():
            raise MS365AuthenticationError(
                f"Certificate file not found: {cert_path}"
            )

        # For PEM format certificates
        if cert_path.suffix.lower() == '.pem':
            with open(cert_path, 'r') as f:
                cert_data = f.read()
            # Parse PEM to get private key and certificate
            private_key = cert_data  # Simplified - in production parse properly
        else:
            # For PFX/PKCS12 format
            # MSAL can handle PFX directly with thumbprint
            private_key = str(cert_path)

        authority = f"https://login.microsoftonline.com/{self.tenant_id}"

        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=authority,
            client_credential={
                "private_key": private_key,
                "thumbprint": settings.MS365_CERTIFICATE_THUMBPRINT,
                "passphrase": cert_password if cert_password else None,
            }
        )

        # Request token for Microsoft Graph
        scopes = ["https://graph.microsoft.com/.default"]
        result = app.acquire_token_for_client(scopes=scopes)

        if "access_token" in result:
            self._access_token = result["access_token"]
            # Token typically valid for 1 hour
            self._token_expiry = timezone.now() + timedelta(minutes=55)
            logger.info("Successfully authenticated with Graph API using certificate")
            return True
        else:
            error = result.get("error_description", result.get("error", "Unknown error"))
            raise MS365AuthenticationError(f"Certificate authentication failed: {error}")

    def _authenticate_with_secret(self, msal) -> bool:
        """Authenticate using client secret."""
        client_secret = settings.MS365_CLIENT_SECRET

        if not client_secret:
            raise MS365AuthenticationError(
                "MS365_CLIENT_SECRET not configured for secret auth"
            )

        authority = f"https://login.microsoftonline.com/{self.tenant_id}"

        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=authority,
            client_credential=client_secret
        )

        scopes = ["https://graph.microsoft.com/.default"]
        result = app.acquire_token_for_client(scopes=scopes)

        if "access_token" in result:
            self._access_token = result["access_token"]
            self._token_expiry = timezone.now() + timedelta(minutes=55)
            logger.info("Successfully authenticated with Graph API using client secret")
            return True
        else:
            error = result.get("error_description", result.get("error", "Unknown error"))
            raise MS365AuthenticationError(f"Client secret authentication failed: {error}")

    def _ensure_authenticated(self):
        """Ensure we have a valid access token."""
        if not self._access_token or (self._token_expiry and timezone.now() >= self._token_expiry):
            self.authenticate()

    def get_message_traces(
        self,
        start_date: datetime,
        end_date: datetime,
        page_size: int = 1000
    ) -> list[dict[str, Any]]:
        """
        Retrieve message traces using Microsoft Graph API.

        Note: As of Jan 2026, the exact endpoint for message traces
        may be in beta. This implementation uses the Reports API
        and may need adjustment based on the latest Graph API docs.
        """
        try:
            import requests
        except ImportError:
            raise MS365APIError(
                "requests library not installed. "
                "Install it with: pip install requests"
            )

        self._ensure_authenticated()

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        all_traces = []

        # Format dates for API
        # Graph API typically uses ISO 8601 format
        start_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Note: The exact endpoint and parameters may vary
        # As of Jan 2026, message trace via Graph is in preview
        # Check: https://learn.microsoft.com/en-us/graph/api/resources/mailmessage
        #
        # This is a placeholder implementation - adjust based on actual API
        # The real endpoint might be something like:
        # /reports/getMessageTrace(startDateTime={start},endDateTime={end})

        url = f"{self.GRAPH_BETA_URL}/admin/exchange/messageTraces"
        params = {
            "startDateTime": start_str,
            "endDateTime": end_str,
            "$top": page_size,
        }

        try:
            while url:
                response = requests.get(url, headers=headers, params=params)

                if response.status_code == 401:
                    # Token expired, re-authenticate
                    self._access_token = None
                    self._ensure_authenticated()
                    headers["Authorization"] = f"Bearer {self._access_token}"
                    continue

                if response.status_code != 200:
                    raise MS365APIError(
                        f"Graph API error: {response.status_code} - {response.text}"
                    )

                data = response.json()
                traces = data.get("value", [])
                all_traces.extend(traces)

                logger.debug(f"Retrieved {len(traces)} traces, total: {len(all_traces)}")

                # Handle pagination
                url = data.get("@odata.nextLink")
                params = {}  # nextLink includes all params

        except requests.RequestException as e:
            raise MS365APIError(f"Network error calling Graph API: {str(e)}")

        logger.info(f"Retrieved {len(all_traces)} total message traces via Graph API")
        return all_traces


class PowerShellClient(BaseMS365Client):
    """
    Exchange Online PowerShell client for retrieving message traces.

    This client uses subprocess to call PowerShell with the
    ExchangeOnlineManagement module. It's the fallback method
    when Graph API is not available.

    Required:
    - PowerShell 7+ or Windows PowerShell 5.1
    - ExchangeOnlineManagement module installed
    - Exchange.ManageAsApp permission in Azure AD

    Uses Get-MessageTraceV2 cmdlet (recommended as of Jan 2026)
    instead of the legacy Get-MessageTrace.
    """

    def __init__(self):
        super().__init__()
        self._connected = False

    def _get_powershell_executable(self) -> str:
        """Determine the PowerShell executable to use."""
        import shutil

        # Prefer PowerShell 7 (pwsh) over Windows PowerShell
        pwsh = shutil.which('pwsh')
        if pwsh:
            return pwsh

        powershell = shutil.which('powershell')
        if powershell:
            return powershell

        raise MS365APIError(
            "PowerShell not found. Install PowerShell 7: "
            "https://docs.microsoft.com/en-us/powershell/scripting/install/installing-powershell"
        )

    def authenticate(self) -> bool:
        """
        Authenticate with Exchange Online using PowerShell.

        This doesn't actually maintain a persistent connection,
        but validates that we can connect.
        """
        # We'll authenticate when running the actual command
        # Just validate configuration here
        auth_method = settings.MS365_AUTH_METHOD

        if auth_method == 'certificate':
            if not settings.MS365_CERTIFICATE_THUMBPRINT:
                raise MS365AuthenticationError(
                    "MS365_CERTIFICATE_THUMBPRINT required for PowerShell certificate auth"
                )
            if not settings.MS365_ORGANIZATION:
                raise MS365AuthenticationError(
                    "MS365_ORGANIZATION required for PowerShell auth "
                    "(e.g., 'contoso.onmicrosoft.com')"
                )
        else:
            if not settings.MS365_CLIENT_SECRET:
                raise MS365AuthenticationError(
                    "MS365_CLIENT_SECRET required for PowerShell secret auth"
                )

        logger.info("PowerShell client configuration validated")
        return True

    def get_message_traces(
        self,
        start_date: datetime,
        end_date: datetime,
        page_size: int = 1000
    ) -> list[dict[str, Any]]:
        """
        Retrieve message traces using Exchange Online PowerShell.

        Uses Get-MessageTraceV2 cmdlet which is the recommended
        cmdlet as of January 2026 (replaces legacy Get-MessageTrace).
        """
        ps_executable = self._get_powershell_executable()

        # Format dates for PowerShell
        start_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Build the PowerShell script
        auth_method = settings.MS365_AUTH_METHOD

        if auth_method == 'certificate':
            connect_cmd = f'''
Connect-ExchangeOnline `
    -CertificateThumbprint "{settings.MS365_CERTIFICATE_THUMBPRINT}" `
    -AppId "{self.client_id}" `
    -Organization "{settings.MS365_ORGANIZATION}" `
    -ShowBanner:$false
'''
        else:
            # Client secret auth - requires creating a credential object
            connect_cmd = f'''
$secureSecret = ConvertTo-SecureString -String "{settings.MS365_CLIENT_SECRET}" -AsPlainText -Force
$credential = New-Object System.Management.Automation.PSCredential("{self.client_id}", $secureSecret)

# Note: Client secret auth with Connect-ExchangeOnline is more complex
# Certificate auth is strongly recommended for unattended scenarios
Connect-ExchangeOnline `
    -AppId "{self.client_id}" `
    -Organization "{settings.MS365_ORGANIZATION}" `
    -Credential $credential `
    -ShowBanner:$false
'''

        # PowerShell script to retrieve message traces
        # Uses Get-MessageTraceV2 (recommended) with fallback to Get-MessageTrace
        ps_script = f'''
$ErrorActionPreference = "Stop"

try {{
    # Import module
    Import-Module ExchangeOnlineManagement -ErrorAction Stop

    # Connect to Exchange Online
    {connect_cmd}

    # Get message traces using the V2 cmdlet (recommended as of Jan 2026)
    # V2 cmdlet provides better performance and additional fields
    $traces = @()

    try {{
        $traces = Get-MessageTraceV2 `
            -StartDate "{start_str}" `
            -EndDate "{end_str}" `
            -PageSize {page_size} `
            -ErrorAction Stop |
            Select-Object MessageId, Received, SenderAddress, RecipientAddress, `
                Subject, Status, ToIP, FromIP, Size, MessageTraceId
    }}
    catch {{
        # Fallback to legacy cmdlet if V2 not available
        Write-Warning "Get-MessageTraceV2 not available, using Get-MessageTrace"
        $traces = Get-MessageTrace `
            -StartDate "{start_str}" `
            -EndDate "{end_str}" `
            -PageSize {page_size} `
            -ErrorAction Stop |
            Select-Object MessageId, Received, SenderAddress, RecipientAddress, `
                Subject, Status, ToIP, FromIP, Size, MessageTraceId
    }}

    # Output as JSON
    $traces | ConvertTo-Json -Depth 10 -Compress

    # Disconnect
    Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue
}}
catch {{
    Write-Error $_.Exception.Message
    exit 1
}}
'''

        # Write script to temp file and execute
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.ps1',
            delete=False
        ) as f:
            f.write(ps_script)
            script_path = f.name

        try:
            result = subprocess.run(
                [ps_executable, '-NoProfile', '-NonInteractive', '-File', script_path],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown PowerShell error"
                raise MS365APIError(f"PowerShell error: {error_msg}")

            # Parse JSON output
            output = result.stdout.strip()
            if not output:
                logger.info("No message traces found for the specified date range")
                return []

            try:
                traces = json.loads(output)
                # Handle single result (not in array)
                if isinstance(traces, dict):
                    traces = [traces]
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse PowerShell output: {output[:500]}")
                raise MS365APIError(f"Invalid JSON from PowerShell: {str(e)}")

            logger.info(f"Retrieved {len(traces)} message traces via PowerShell")
            return traces

        except subprocess.TimeoutExpired:
            raise MS365APIError("PowerShell command timed out (5 minute limit)")

        finally:
            # Clean up temp file
            Path(script_path).unlink(missing_ok=True)


def get_ms365_client() -> BaseMS365Client:
    """
    Factory function to get the appropriate MS365 client based on configuration.

    Returns GraphAPIClient if MS365_API_METHOD is 'graph', otherwise PowerShellClient.
    """
    api_method = settings.MS365_API_METHOD

    if api_method == 'graph':
        logger.info("Using Microsoft Graph API client")
        return GraphAPIClient()
    else:
        logger.info("Using Exchange Online PowerShell client")
        return PowerShellClient()


def normalize_trace_data(trace: dict, source: str = 'graph') -> dict:
    """
    Normalize message trace data from different sources to a common format.

    Args:
        trace: Raw trace data from API
        source: 'graph' or 'powershell'

    Returns:
        Normalized trace dictionary
    """
    if source == 'powershell':
        # Map PowerShell field names to our model fields
        return {
            'message_id': trace.get('MessageId', ''),
            'received_date': trace.get('Received'),
            'sender': trace.get('SenderAddress', ''),
            'recipient': trace.get('RecipientAddress', ''),
            'subject': trace.get('Subject', ''),
            'status': trace.get('Status', 'Unknown'),
            'size': trace.get('Size', 0) or 0,
            'event_data': {
                'to_ip': trace.get('ToIP'),
                'from_ip': trace.get('FromIP'),
                'message_trace_id': trace.get('MessageTraceId'),
            },
            'raw_json': trace,
        }
    else:  # graph
        # Map Graph API field names (may vary based on actual API response)
        return {
            'message_id': trace.get('internetMessageId', trace.get('messageId', '')),
            'received_date': trace.get('receivedDateTime', trace.get('received')),
            'sender': trace.get('sender', {}).get('emailAddress', {}).get('address', '')
                      if isinstance(trace.get('sender'), dict)
                      else trace.get('senderAddress', ''),
            'recipient': trace.get('recipientAddress', ''),
            'subject': trace.get('subject', ''),
            'status': trace.get('status', 'Unknown'),
            'size': trace.get('size', 0) or 0,
            'event_data': trace.get('eventData', {}),
            'raw_json': trace,
        }
