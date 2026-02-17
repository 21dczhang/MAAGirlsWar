# PowerShell script to download and extract the latest version of MAAGirlsWar

# Set variables
$DownloadPath = "$env:TEMP\MaaLatest.zip"
$ExtractPath = "C:\Users\Aurora\Desktop"
$RepoUrl = "https://api.github.com/repos/21dczhang/MAAGirlsWar/releases/latest"

Write-Host "Getting latest MAAGirlsWar release info..."

try {
    # Get latest release information
    $ReleaseInfo = Invoke-RestMethod -Uri $RepoUrl -Method Get
    
    # Find asset file matching pattern
    $Asset = $ReleaseInfo.assets | Where-Object { $_.name -match "^Maa.*-win-x86_64-v\d+\.\d+\.\d+\.zip$" }
    
    if ($null -eq $Asset) {
        Write-Error "No matching archive file found"
        exit 1
    }
    
    $DownloadUrl = $Asset.browser_download_url
    $FileName = $Asset.name
    
    Write-Host "Found latest version: $FileName"
    Write-Host "Starting download..."
    
    # Download file using .NET WebClient to avoid potential issues with Invoke-WebRequest
    $WebClient = New-Object System.Net.WebClient
    $WebClient.DownloadFile($DownloadUrl, $DownloadPath)
    $WebClient.Dispose()
    
    Write-Host "Download completed, saved to: $DownloadPath"
    
    # Verify the downloaded file is a valid zip
    try {
        $ZipArchive = [System.IO.Compression.ZipFile]::OpenRead($DownloadPath)
        $ZipArchive.Dispose()
    }
    catch {
        Write-Error "Downloaded file is not a valid ZIP archive: $($_.Exception.Message)"
        Remove-Item $DownloadPath -ErrorAction SilentlyContinue
        exit 1
    }
    
    # Check if extraction path exists
    if (!(Test-Path $ExtractPath)) {
        New-Item -ItemType Directory -Path $ExtractPath -Force
    }
    
    # Create destination folder name without extension
    $DestinationPath = Join-Path $ExtractPath ([System.IO.Path]::GetFileNameWithoutExtension($FileName))
    
    # Ensure destination directory doesn't already exist to prevent conflicts
    if (Test-Path $DestinationPath) {
        Remove-Item -Path $DestinationPath -Recurse -Force
    }
    
    # Extract file using .NET compression methods
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($DownloadPath, $DestinationPath)
    
    Write-Host "Extraction completed, extracted to: $DestinationPath"
    
    # Clean up temporary download file
    Remove-Item $DownloadPath -Force
    
    Write-Host "Operation completed!"
}
catch {
    Write-Error "Operation failed: $($_.Exception.Message)"
    if (Test-Path $DownloadPath) {
        Remove-Item $DownloadPath -ErrorAction SilentlyContinue
    }
}
