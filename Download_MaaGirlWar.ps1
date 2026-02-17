# PowerShell script to download and extract the latest version of MAAGirlsWar

# Set variables
$DownloadPath = "$env:TEMP\MaaLatest.zip"
$ExtractPath = "C:\Users\Aurora\Desktop"
$TargetFolderName = "MaaGirlsWar"
$RepoUrl = "https://api.github.com/repos/21dczhang/MAAGirlsWar/releases/latest"

Write-Host "Getting latest MAAGirlsWar release info..."

try {
    # Get latest release information
    $ReleaseInfo = Invoke-RestMethod -Uri $RepoUrl -Method Get
    
    # Find asset file matching the correct pattern (MaaGirlsWar-win-x64.zip)
    $Asset = $ReleaseInfo.assets | Where-Object { $_.name -match "^MaaGirlsWar-win-x64\.zip$" }
    
    if ($null -eq $Asset) {
        Write-Error "No matching archive file found. Available assets:"
        foreach ($availableAsset in $ReleaseInfo.assets) {
            Write-Host "  - $($availableAsset.name)"
        }
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
    
    # Load the required assembly for ZIP operations
    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
    }
    catch {
        Write-Error "Failed to load System.IO.Compression.FileSystem assembly: $($_.Exception.Message)"
        exit 1
    }
    
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
    
    # Define target destination path
    $DestinationPath = Join-Path $ExtractPath $TargetFolderName
    
    # Remove existing MaaGirlsWar folder if it exists
    if (Test-Path $DestinationPath) {
        Write-Host "Removing existing $TargetFolderName folder..."
        Remove-Item -Path $DestinationPath -Recurse -Force
    }
    
    # Create temporary extraction directory
    $TempExtractPath = Join-Path $env:TEMP ([System.IO.Path]::GetRandomFileName())
    New-Item -ItemType Directory -Path $TempExtractPath -Force
    
    # Extract file using .NET compression methods to temporary location
    [System.IO.Compression.ZipFile]::ExtractToDirectory($DownloadPath, $TempExtractPath)
    
    # Find the actual extracted content (there might be a subfolder inside the zip)
    $ExtractedItems = Get-ChildItem -Path $TempExtractPath
    if ($ExtractedItems.Count -eq 1 -and $ExtractedItems[0].PSIsContainer) {
        # If there's only one folder in the extracted content, use that folder's contents
        $ActualContentPath = $ExtractedItems[0].FullName
    }
    else {
        # Otherwise, use the entire temp extraction directory
        $ActualContentPath = $TempExtractPath
    }
    
    # Move the content to the final destination with the fixed name
    Move-Item -Path $ActualContentPath -Destination $DestinationPath -Force
    
    # Clean up temporary extraction directory
    if (Test-Path $TempExtractPath) {
        Remove-Item -Path $TempExtractPath -Recurse -Force
    }
    
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
    
    # Clean up temporary extraction directory if it exists
    $TempExtractPath = Join-Path $env:TEMP ([System.IO.Path]::GetRandomFileName())
    if (Test-Path $TempExtractPath) {
        Remove-Item -Path $TempExtractPath -ErrorAction SilentlyContinue
    }
}
