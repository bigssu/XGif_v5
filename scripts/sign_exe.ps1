# sign_exe.ps1 — XGif EXE/인스톨러 코드 서명
#
# 사용법:
#   powershell.exe -ExecutionPolicy Bypass -File scripts\sign_exe.ps1 -PfxPath signing\XGif_CodeSign.pfx -Password "XGif2024!"
#   powershell.exe -ExecutionPolicy Bypass -File scripts\sign_exe.ps1 -PfxPath signing\XGif_CodeSign.pfx -Password "XGif2024!" -ExePaths "dist\XGif.exe","dist\XGif_Setup_0.56.exe"

param(
    [Parameter(Mandatory=$true)]
    [string]$PfxPath,

    [Parameter(Mandatory=$true)]
    [string]$Password,

    [string[]]$ExePaths = @("dist\XGif.exe"),

    [string]$TimestampUrl = "http://timestamp.digicert.com",

    [string]$Description = "XGif Screen Recorder"
)

$ErrorActionPreference = "Stop"

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

    & $signtool sign `
        /f "$PfxFullPath" `
        /p "$Password" `
        /fd SHA256 `
        /td SHA256 `
        /tr "$TimestampUrl" `
        /d "$Description" `
        "$exePath"

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
