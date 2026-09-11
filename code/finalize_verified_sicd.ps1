[CmdletBinding()]
param(
    [string]$Workspace = "D:\Dati Tesi\Umbra",
    [string]$PartRelativePath = "Vandenberg\2025-02-16-18-55-44_UMBRA-10_SICD.nitf.part",
    [string]$FinalRelativePath = "Vandenberg\2025-02-16-18-55-44_UMBRA-10_SICD.nitf",
    [string]$VerificationRelativePath = "Vandenberg\metadata\SICD_MULTIPART_ETAG_VERIFICATION.json",
    [Int64]$ExpectedSize = 11478596733
)

$ErrorActionPreference = "Stop"

function Resolve-ContainedPath {
    param([string]$Root, [string]$Candidate)
    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $candidateFull = [System.IO.Path]::GetFullPath($Candidate)
    if (-not $candidateFull.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing path outside workspace: $candidateFull"
    }
    return $candidateFull
}

$workspaceFull = [System.IO.Path]::GetFullPath($Workspace)
$partPath = Resolve-ContainedPath $workspaceFull (Join-Path $workspaceFull $PartRelativePath)
$finalPath = Resolve-ContainedPath $workspaceFull (Join-Path $workspaceFull $FinalRelativePath)
$verificationPath = Resolve-ContainedPath $workspaceFull (Join-Path $workspaceFull $VerificationRelativePath)

if (-not (Test-Path -LiteralPath $partPath -PathType Leaf)) {
    throw "Verified partial file does not exist: $partPath"
}
if (Test-Path -LiteralPath $finalPath) {
    throw "Refusing to overwrite existing final SICD: $finalPath"
}
if (-not (Test-Path -LiteralPath $verificationPath -PathType Leaf)) {
    throw "Verification report does not exist: $verificationPath"
}

$verification = Get-Content -LiteralPath $verificationPath -Raw | ConvertFrom-Json
if (-not $verification.passed) {
    throw "Multipart ETag verification did not pass"
}
$partFull = [System.IO.Path]::GetFullPath($partPath)
$reportedFull = [System.IO.Path]::GetFullPath([string]$verification.path)
if ($partFull -ne $reportedFull) {
    throw "Verification report path does not match partial file"
}
$actualSize = (Get-Item -LiteralPath $partPath).Length
if ($actualSize -ne $ExpectedSize -or [Int64]$verification.size_bytes -ne $ExpectedSize) {
    throw "Exact-size verification failed before finalization"
}

Move-Item -LiteralPath $partPath -Destination $finalPath
Write-Output "FINALIZED=$finalPath"
Write-Output "SIZE=$((Get-Item -LiteralPath $finalPath).Length)"
