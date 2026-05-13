# sign_exe.ps1 — XGif EXE/인스톨러 코드 서명
#
# 사용법 (권장 1 — 환경변수, 명령행 노출 없음):
#   $env:XGIF_SIGN_PASSWORD = '<your-pfx-password>'  # 또는 XGIF_PFX_PASSWORD (alias)
#   powershell.exe -ExecutionPolicy Bypass -File scripts\sign_exe.ps1 -PfxPath signing\XGif_CodeSign.pfx
#
# 사용법 (권장 2 — Read-Host -AsSecureString 으로 대화형 입력):
#   $sp = Read-Host 'PFX password' -AsSecureString
#   powershell.exe -ExecutionPolicy Bypass -File scripts\sign_exe.ps1 -PfxPath signing\XGif_CodeSign.pfx -Password $sp
#
# 비권장: 평문 -Password 파라미터는 더 이상 지원하지 않습니다. SecureString 만 허용.

param(
    [Parameter(Mandatory=$true)]
    [string]$PfxPath,

    [System.Security.SecureString]$Password,

    [string[]]$ExePaths = @("dist\XGif.exe"),

    [string]$TimestampUrl = "http://timestamp.digicert.com",

    [string]$Description = "XGif Screen Recorder"
)

$ErrorActionPreference = "Stop"

# 환경변수 fallback: XGIF_SIGN_PASSWORD 우선, 없으면 XGIF_PFX_PASSWORD (alias) 시도.
# 평문 환경변수는 즉시 SecureString 으로 승격하고 원본 변수에서 지운다.
if (-not $Password) {
    $envPlain = $env:XGIF_SIGN_PASSWORD
    if (-not $envPlain) { $envPlain = $env:XGIF_PFX_PASSWORD }
    if ($envPlain) {
        $Password = ConvertTo-SecureString -String $envPlain -Force -AsPlainText
        Remove-Variable envPlain -ErrorAction SilentlyContinue
        $env:XGIF_SIGN_PASSWORD = $null
        $env:XGIF_PFX_PASSWORD = $null
    }
}
if (-not $Password) {
    Write-Host "[ERROR] Password not provided. Pass -Password as SecureString, or set XGIF_SIGN_PASSWORD / XGIF_PFX_PASSWORD env var."
    exit 1
}

# ── signtool.exe 자동 감지 ──
function Find-SignTool {
    # 1) PATH에서 찾기
    $inPath = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($inPath) { return $inPath.Source }

    # 2) Windows SDK 경로 탐색
    $sdkRoots = @(
        "${env:ProgramFiles(x86)}\Windows Kits\10\bin",
        "${env:ProgramFiles}\Windows Kits\10\bin"
    )

    foreach ($root in $sdkRoots) {
        if (-not (Test-Path $root)) { continue }

        # 최신 SDK 버전 폴더 우선
        $versions = Get-ChildItem -Path $root -Directory | Where-Object { $_.Name -match '^\d+\.' } | Sort-Object Name -Descending
        foreach ($ver in $versions) {
            $candidate = Join-Path $ver.FullName "x64\signtool.exe"
            if (Test-Path $candidate) { return $candidate }
            $candidate = Join-Path $ver.FullName "x86\signtool.exe"
            if (Test-Path $candidate) { return $candidate }
        }
    }

    return $null
}

# ── 메인 ──
Write-Host ""
Write-Host "=== XGif Code Signing ==="
Write-Host ""

# PFX 파일 확인
$PfxFullPath = Resolve-Path $PfxPath -ErrorAction SilentlyContinue
if (-not $PfxFullPath) {
    Write-Host "[ERROR] PFX file not found: $PfxPath"
    Write-Host "        Run scripts\create_selfsign_cert.ps1 first."
    exit 1
}
Write-Host "[OK] PFX: $PfxFullPath"

# signtool 찾기
$signtool = Find-SignTool
if (-not $signtool) {
    Write-Host "[ERROR] signtool.exe not found."
    Write-Host "        Install Windows SDK or add signtool.exe to PATH."
    Write-Host "        https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/"
    exit 1
}
Write-Host "[OK] signtool: $signtool"
Write-Host ""

# 각 EXE 서명
$failed = 0
foreach ($exePath in $ExePaths) {
    if (-not (Test-Path $exePath)) {
        Write-Host "[SKIP] File not found: $exePath"
        continue
    }

    Write-Host "Signing: $exePath"

    # SecureString → 평문 추출은 signtool 호출 직전에만, 변수는 즉시 폐기.
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password)
    try {
        $plain = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
        & $signtool sign `
            /f "$PfxFullPath" `
            /p "$plain" `
            /fd SHA256 `
            /td SHA256 `
            /tr "$TimestampUrl" `
            /d "$Description" `
            "$exePath"
    } finally {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        Remove-Variable plain -ErrorAction SilentlyContinue
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to sign: $exePath"
        $failed++
    } else {
        Write-Host "[OK] Signed: $exePath"
    }
    Write-Host ""
}

if ($failed -gt 0) {
    Write-Host "[ERROR] $failed file(s) failed to sign."
    exit 1
}

Write-Host "=== All files signed successfully ==="
