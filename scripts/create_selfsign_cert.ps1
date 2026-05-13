# create_selfsign_cert.ps1 — XGif 코드 서명용 셀프 서명 인증서 생성
# 용도: 로컬 개발/테스트용
#
# 사용법 (대화형 — 권장):
#   powershell.exe -ExecutionPolicy Bypass -File scripts\create_selfsign_cert.ps1
#
# 사용법 (환경변수):
#   $env:XGIF_PFX_PASSWORD = '<your-pfx-password>'  # 또는 XGIF_SIGN_PASSWORD (alias)
#   powershell.exe -ExecutionPolicy Bypass -File scripts\create_selfsign_cert.ps1
#
# 사용법 (SecureString):
#   $sp = Read-Host 'PFX password' -AsSecureString
#   powershell.exe -ExecutionPolicy Bypass -File scripts\create_selfsign_cert.ps1 -Password $sp
#
# 비권장: 평문 -Password 파라미터는 더 이상 지원하지 않습니다. SecureString 만 허용.

param(
    [string]$CertName = "XGif Code Signing",
    [System.Security.SecureString]$Password,
    [string]$OutputDir = (Join-Path $PSScriptRoot "..\signing"),
    [int]$ValidYears = 3
)

$ErrorActionPreference = "Stop"

# 환경변수 fallback: XGIF_PFX_PASSWORD / XGIF_SIGN_PASSWORD alias.
if (-not $Password) {
    $envPlain = $env:XGIF_PFX_PASSWORD
    if (-not $envPlain) { $envPlain = $env:XGIF_SIGN_PASSWORD }
    if ($envPlain) {
        $Password = ConvertTo-SecureString -String $envPlain -Force -AsPlainText
        Remove-Variable envPlain -ErrorAction SilentlyContinue
        $env:XGIF_PFX_PASSWORD = $null
        $env:XGIF_SIGN_PASSWORD = $null
    }
}

# 출력 디렉토리 생성
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    Write-Host "[OK] Created directory: $OutputDir"
}

$PfxPath = Join-Path $OutputDir "XGif_CodeSign.pfx"

# 기존 PFX 파일 확인
if (Test-Path $PfxPath) {
    Write-Host "[WARN] PFX file already exists: $PfxPath"
    $confirm = Read-Host "Overwrite? (y/N)"
    if ($confirm -ne "y") {
        Write-Host "Cancelled."
        exit 0
    }
}

Write-Host ""
Write-Host "=== XGif Self-Signed Code Signing Certificate ==="
Write-Host "  Subject:    CN=$CertName"
Write-Host "  Valid for:  $ValidYears years"
Write-Host "  Output:     $PfxPath"
Write-Host ""

# 셀프 서명 인증서 생성
try {
    $cert = New-SelfSignedCertificate `
        -Subject "CN=$CertName" `
        -Type CodeSigningCert `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -NotAfter (Get-Date).AddYears($ValidYears) `
        -KeyAlgorithm RSA `
        -KeyLength 2048 `
        -HashAlgorithm SHA256

    Write-Host "[OK] Certificate created: $($cert.Thumbprint)"
} catch {
    Write-Host "[ERROR] Failed to create certificate: $_"
    exit 1
}

# PFX로 내보내기
try {
    if (-not $Password) {
        $Password = Read-Host "PFX password" -AsSecureString
    }
    Export-PfxCertificate -Cert $cert -FilePath $PfxPath -Password $Password | Out-Null
    Write-Host "[OK] PFX exported: $PfxPath"
} catch {
    Write-Host "[ERROR] Failed to export PFX: $_"
    exit 1
}

# 인증서 저장소에서 제거 (PFX 파일만 유지)
try {
    Remove-Item -Path "Cert:\CurrentUser\My\$($cert.Thumbprint)" -ErrorAction SilentlyContinue
    Write-Host "[OK] Removed certificate from store (PFX file retained)"
} catch {
    Write-Host "[WARN] Could not remove certificate from store: $_"
}

Write-Host ""
Write-Host "=== Done ==="
Write-Host "  PFX: $PfxPath"
Write-Host "  Password: [hidden]"
Write-Host ""
Write-Host "NOTE: This is a self-signed certificate for local testing only."
Write-Host "      For production, use a certificate from a trusted CA."
