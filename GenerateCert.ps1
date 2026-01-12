# Generate a self-signed certificate for Exo-Trace-Archiver
# Run this script in PowerShell on Windows

param(
    [string]$OutputPath = "C:\cert",
    [string]$CertName = "ExoTraceArchiver",
    [string]$Password = "ExoTrace2024!",
    [int]$ValidYears = 2
)

# Create output directory if it doesn't exist
if (-not (Test-Path $OutputPath)) {
    New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null
    Write-Host "Created directory: $OutputPath" -ForegroundColor Green
}

# Generate a self-signed certificate
Write-Host "Generating self-signed certificate..." -ForegroundColor Cyan
$cert = New-SelfSignedCertificate `
    -Subject "CN=$CertName" `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -KeyExportPolicy Exportable `
    -KeySpec Signature `
    -KeyLength 2048 `
    -KeyAlgorithm RSA `
    -HashAlgorithm SHA256 `
    -NotAfter (Get-Date).AddYears($ValidYears)

# Export the certificate (public key only) - for uploading to Azure AD
$cerPath = Join-Path $OutputPath "$CertName.cer"
Export-Certificate -Cert $cert -FilePath $cerPath | Out-Null
Write-Host "Exported public certificate: $cerPath" -ForegroundColor Green

# Export the private key as PFX with password
$pfxPath = Join-Path $OutputPath "$CertName.pfx"
$securePassword = ConvertTo-SecureString -String $Password -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $securePassword | Out-Null
Write-Host "Exported PFX certificate: $pfxPath" -ForegroundColor Green

# Display summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Yellow
Write-Host "Certificate Generation Complete!" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "Certificate Details:" -ForegroundColor Cyan
Write-Host "  Subject:     CN=$CertName"
Write-Host "  Thumbprint:  $($cert.Thumbprint)"
Write-Host "  Expires:     $($cert.NotAfter)"
Write-Host ""
Write-Host "Files Created:" -ForegroundColor Cyan
Write-Host "  Public Cert: $cerPath"
Write-Host "  PFX (Private): $pfxPath"
Write-Host "  Password:    $Password"
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "  1. Upload '$CertName.cer' to Azure AD App Registration"
Write-Host "     (Certificates & secrets > Certificates > Upload)"
Write-Host ""
Write-Host "  2. Upload '$CertName.pfx' to Exo-Trace-Archiver tenant settings"
Write-Host ""
Write-Host "  3. Enter the following in tenant settings:"
Write-Host "     - Certificate Thumbprint: $($cert.Thumbprint)"
Write-Host "     - Certificate Password:   $Password"
Write-Host ""
Write-Host "========================================" -ForegroundColor Yellow

# Copy thumbprint to clipboard if possible
try {
    $cert.Thumbprint | Set-Clipboard
    Write-Host "Thumbprint copied to clipboard!" -ForegroundColor Green
} catch {
    # Clipboard not available
}
