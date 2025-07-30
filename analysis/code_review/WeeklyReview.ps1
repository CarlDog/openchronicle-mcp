# Set directories
$sourceDir = "D:\OneDrive\GitHub\OpenChronicle\openchronicle-core\core"
$logDir = "D:\OneDrive\GitHub\OpenChronicle\openchronicle-core\analysis\code_review"

# Today's date in formats
$today = Get-Date -Format "yyyy-MM-dd"
$fileDate = Get-Date -Format "yyyyMMdd"

# Create output directory if it doesn't exist
$todayLogDir = Join-Path $logDir $today
if (-not (Test-Path $todayLogDir)) {
    New-Item -ItemType Directory -Path $todayLogDir | Out-Null
}

# Process each Python file
Get-ChildItem $sourceDir -Recurse -Include *.py | ForEach-Object {
    if ($_.Name -eq "__init__.py") {
        Write-Host "  Skipping __init__.py"
        return
    }

    $safeName = $_.BaseName
    $logFileName = "WizardCoder_${safeName}_${fileDate}.txt"
    $logPath = Join-Path $todayLogDir $logFileName

    if (Test-Path $logPath) {
        Write-Host "  Already processed $($_.Name), skipping..."
        return
    }

    Write-Host "`nStarting analysis on $($_.FullName)"
    $startTime = Get-Date

    $code = Get-Content $_.FullName -Raw
    $lineCount = ($code -split "`n").Count
    $prompt = "Analyze the following Python code for opportunities to refactor and deduplicate logic. Suggest improvements.`n`n$code"

    $output = $prompt | ollama run wizardcoder:13b-python

    $endTime = Get-Date
    $elapsed = $endTime - $startTime

    $header = @(
        "===== Analysis Report ====="
        "File: $($_.Name)"
        "Lines: $lineCount"
        "Processed: $($startTime.ToString("yyyy-MM-dd HH:mm:ss"))"
        "Duration: $($elapsed.Minutes)m $($elapsed.Seconds)s"
        "==========================="
        ""
    ) -join "`n"

    ($header + $output) | Out-File -Encoding utf8 -FilePath $logPath

    Write-Host "  Saved output to $logPath"
    Write-Host "  Took $($elapsed.Minutes)m $($elapsed.Seconds)s"

    Start-Sleep -Seconds 30
}
