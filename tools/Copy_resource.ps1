$source = ".\assets\resource"
$destination = "C:\Users\Aurora\Desktop\MaaGirlsWar\resource"

Copy-Item -Path "$source\*" -Destination $destination -Recurse -Force

Write-Host "Done!" -ForegroundColor Green