$content = Get-Content C:\Users\Aster\Desktop\Proyecto\vegeta-microservicio\targets-parse.txt -Raw
$content2 = $content.Replace('POST http://extract.localhost/extract', 'POST http://127.0.0.1/extract')
# Use a different approach - split by double newline (target separator), process each target
$targets = $content2 -split '\n\n'
$newTargets = @()
foreach ($target in $targets) {
    if ($target.Trim() -eq '') { continue }
    $lines = $target -split "`n"
    # Insert Host header after first line (POST line)
    $newLines = @($lines[0], 'Host: extract.localhost') + $lines[1..($lines.Count-1)]
    $newTargets += $newLines -join "`n"
}
$content3 = $newTargets -join "`n`n"
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText('C:\Users\Aster\Desktop\Proyecto\vegeta-microservicio\targets-parse-local.txt', $content3, $utf8NoBom)
Write-Host "Done. First 10 lines:"
$lines = $content3 -split "`n"
for ($i=0; $i -lt 10; $i++) { Write-Host "[$i] $($lines[$i])" }