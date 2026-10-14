$content = Get-Content C:\Users\Aster\Desktop\Proyecto\vegeta-microservicio\targets-parse.txt -Raw
$content2 = $content.Replace('POST http://extract.localhost/extract', 'POST http://127.0.0.1/extract')
$lines = $content2 -split "`n"
Write-Host "First 5 lines after replace:"
for ($i=0; $i -lt 5; $i++) { Write-Host "[$i] $($lines[$i])" }