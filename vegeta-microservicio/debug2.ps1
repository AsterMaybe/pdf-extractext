$content = Get-Content C:\Users\Aster\Desktop\Proyecto\vegeta-microservicio\targets-parse.txt -Raw
$content2 = $content.Replace('POST http://extract.localhost/extract', 'POST http://127.0.0.1/extract')
$content3 = $content2 -replace '(?m)^(POST http://127\.0\.0\.1/extract)$', "$1`nHost: extract.localhost"
$lines = $content3 -split "`n"
Write-Host "First 10 lines after second replace:"
for ($i=0; $i -lt 10; $i++) { Write-Host "[$i] $($lines[$i])" }