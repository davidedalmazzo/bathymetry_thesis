[CmdletBinding()]
param(
    [string]$Workspace = "D:\Dati Tesi\Umbra",
    [string]$Url = "https://umbra-open-data-catalog.s3.us-west-2.amazonaws.com/sar-data/task-data/f2f8c71e-6aec-4358-acda-93c5e68e8b4b/2025-02-16-18-55-44_UMBRA-10/2025-02-16-18-55-44_UMBRA-10_SICD.nitf",
    [Int64]$ExpectedSize = 11478596733,
    [string]$ExpectedETag = "f06d503551fb567303477152aee18652-219",
    [string]$FileName = "2025-02-16-18-55-44_UMBRA-10_SICD.nitf"
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
$outputDirectory = Resolve-ContainedPath $workspaceFull (Join-Path $workspaceFull "Vandenberg")
$finalPath = Resolve-ContainedPath $workspaceFull (Join-Path $outputDirectory $FileName)
$partPath = Resolve-ContainedPath $workspaceFull ($finalPath + ".part")

New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null

if (Test-Path -LiteralPath $finalPath) {
    $existingFinalSize = (Get-Item -LiteralPath $finalPath).Length
    if ($existingFinalSize -eq $ExpectedSize) {
        Write-Output "Final SICD already exists with expected size: $finalPath"
        exit 0
    }
    throw "Final path exists with unexpected size ($existingFinalSize): $finalPath"
}

$headOutput = & curl.exe --fail --silent --show-error --location --head $Url
if ($LASTEXITCODE -ne 0) {
    throw "HEAD request failed with curl exit code $LASTEXITCODE"
}
$headText = ($headOutput -join "`n")
$lengthMatches = [regex]::Matches($headText, '(?im)^content-length:\s*(\d+)\s*$')
$etagMatches = [regex]::Matches($headText, '(?im)^etag:\s*"?([^"\r\n]+)"?\s*$')
if ($lengthMatches.Count -eq 0 -or $etagMatches.Count -eq 0) {
    throw "Could not parse Content-Length and ETag from HTTP headers"
}
$remoteSize = [Int64]$lengthMatches[$lengthMatches.Count - 1].Groups[1].Value
$remoteETag = $etagMatches[$etagMatches.Count - 1].Groups[1].Value.Trim()
if ($remoteSize -ne $ExpectedSize) {
    throw "Remote Content-Length mismatch: expected $ExpectedSize, got $remoteSize"
}
if ($remoteETag -ne $ExpectedETag) {
    throw "Remote ETag mismatch: expected $ExpectedETag, got $remoteETag"
}

$partialSize = 0L
if (Test-Path -LiteralPath $partPath) {
    $partialSize = (Get-Item -LiteralPath $partPath).Length
    if ($partialSize -gt $ExpectedSize) {
        throw "Partial file is larger than expected: $partialSize > $ExpectedSize"
    }
}
$remaining = $ExpectedSize - $partialSize
$driveRoot = [System.IO.Path]::GetPathRoot($outputDirectory)
$drive = Get-PSDrive -Name $driveRoot.Substring(0, 1)
$safetyMargin = 1073741824L
if ($drive.Free -lt ($remaining + $safetyMargin)) {
    throw "Insufficient free space: need at least $($remaining + $safetyMargin) bytes, have $($drive.Free)"
}

Write-Output "Remote preflight verified: size=$remoteSize ETag=$remoteETag"
Write-Output "Downloading/resuming at byte $partialSize into $partPath"
& curl.exe --fail --location --continue-at - --retry 12 --retry-delay 5 --retry-all-errors --output $partPath $Url
if ($LASTEXITCODE -ne 0) {
    throw "Download failed with curl exit code $LASTEXITCODE; resumable partial file retained"
}

$downloadedSize = (Get-Item -LiteralPath $partPath).Length
if ($downloadedSize -ne $ExpectedSize) {
    throw "Downloaded size mismatch: expected $ExpectedSize, got $downloadedSize"
}

Write-Output "SIZE_VERIFIED=$downloadedSize"
Write-Output "PART_PATH=$partPath"
Write-Output "The .part file is intentionally retained pending multipart-ETag verification."
