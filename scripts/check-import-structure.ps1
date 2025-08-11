# 📁 OpenChronicle Architecture Guard - Import Structure
# Validates import patterns for maintainability

Write-Output "🔍 Validating import patterns..."

# Check for deep relative imports (prefer absolute)
$DEEP_RELATIVES = Select-String -Path "src\**\*.py" -Pattern "from \.\.\." -Recurse 2>$null

if ($DEEP_RELATIVES) {
    Write-Output "⚠️ WARNING: Deep relative imports detected (prefer absolute):"
    Write-Output $DEEP_RELATIVES
    Write-Output ""
    Write-Output "💡 Consider converting to absolute imports:"
    Write-Output "  from ...deep.path → from src.openchronicle.deep.path"
    Write-Output ""
}

# Count import patterns for metrics
$ABSOLUTE_IMPORTS = (Select-String -Path "src\**\*.py" -Pattern "from src\.openchronicle" -Recurse 2>$null | Measure-Object).Count
$RELATIVE_IMPORTS = (Select-String -Path "src\**\*.py" -Pattern "from \." -Recurse 2>$null | Measure-Object).Count

Write-Output "📊 Import pattern metrics:"
Write-Output "  Absolute imports: $ABSOLUTE_IMPORTS"
Write-Output "  Relative imports: $RELATIVE_IMPORTS"

Write-Output "✅ Import structure validation complete"
