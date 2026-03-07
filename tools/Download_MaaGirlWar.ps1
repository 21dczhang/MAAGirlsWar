# PowerShell script to download and update MAAGirlsWar contents

# Set variables
$DownloadPath = "$env:TEMP\MaaLatest.zip"
$ExtractPath = "$Home\Desktop"
$TargetFolderName = "MaaGirlsWar"
$RepoUrl = "https://api.github.com/repos/21dczhang/MAAGirlsWar/releases/latest"
$DestinationPath = Join-Path $ExtractPath $TargetFolderName

Write-Host "Fetching latest MAAGirlsWar release information..." -ForegroundColor Cyan

try {
    # 1. Get latest release metadata from GitHub API
    $ReleaseInfo = Invoke-RestMethod -Uri $RepoUrl -Method Get
    
    # 2. Filter for the specific asset (MAAGirlsWar-win-x86_64-*-Full.zip)
    $Asset = $ReleaseInfo.assets | Where-Object {
        $_.name -like "MAAGirlsWar-win-x86_64-*-Full.zip"
    }
    
    if ($null -eq $Asset) {
        Write-Error "No matching archive file found on GitHub."
        exit 1
    }
    
    $DownloadUrl = $Asset.browser_download_url
    Write-Host "Latest version found: $($Asset.name)" -ForegroundColor Green
    
    # 3. Download the ZIP file
    Write-Host "Starting download..."
    $WebClient = New-Object System.Net.WebClient
    $WebClient.DownloadFile($DownloadUrl, $DownloadPath)
    $WebClient.Dispose()
    
    # 4. Prepare the target directory
    if (!(Test-Path $DestinationPath)) {
        Write-Host "Target folder does not exist. Creating: $DestinationPath"
        New-Item -ItemType Directory -Path $DestinationPath -Force
    } else {
        # --- Core Change: Clear contents only, keep the root folder ---
        Write-Host "Cleaning existing contents in $TargetFolderName..." -ForegroundColor Yellow
        Get-ChildItem -Path $DestinationPath | Remove-Item -Recurse -Force
    }
    
    # 5. Extract to a temporary location
    $TempExtractPath = Join-Path $env:TEMP ([System.IO.Path]::GetRandomFileName())
    New-Item -ItemType Directory -Path $TempExtractPath -Force
    
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($DownloadPath, $TempExtractPath)
    
    # 6. Handle nested folders and move content to the destination
    $ExtractedItems = Get-ChildItem -Path $TempExtractPath
    if ($ExtractedItems.Count -eq 1 -and $ExtractedItems[0].PSIsContainer) {
        # If the ZIP contains a single root folder, use its children
        $ActualContentPath = $ExtractedItems[0].FullName
    } else {
        $ActualContentPath = $TempExtractPath
    }
    
    # Move new files into the cleared MaaGirlsWar folder
    Get-ChildItem -Path $ActualContentPath | Move-Item -Destination $DestinationPath -Force
    
    # 7. Cleanup
    Remove-Item $DownloadPath -Force
    Remove-Item $TempExtractPath -Recurse -Force
    
    Write-Host "Update successful! Files are located at: $DestinationPath" -ForegroundColor Green
}
catch {
    Write-Error "An error occurred: $($_.Exception.Message)"
}