$curlArgs = @("-X", "POST", "http://localhost:8000/start")

Get-ChildItem "$PSScriptRoot\resumes\*.pdf" | ForEach-Object {
    $curlArgs += "-F"
    $curlArgs += ('files=@"{0}"' -f $_.FullName)
}

& curl.exe @curlArgs
