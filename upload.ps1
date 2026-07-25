$body = @{ count = 500 } | ConvertTo-Json

$result = Invoke-RestMethod -Method POST `
  -Uri "http://localhost:8000/start" `
  -ContentType "application/json" `
  -Body $body

Write-Host ""
Write-Host "=== Batch Complete ===" -ForegroundColor Green
Write-Host ("Tasks:      {0}" -f $result.task_count)
Write-Host ("Total time: {0} s" -f $result.total_time_seconds)
Write-Host ("Avg / task: {0} s" -f $result.avg_time_per_task_seconds)
Write-Host ("Message:    {0}" -f $result.message)
Write-Host ""
