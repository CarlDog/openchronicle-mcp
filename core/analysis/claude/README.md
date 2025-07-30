# OpenChronicle Core Analysis Suite

This directory contains Claude-powered architecture analysis tools for monitoring and improving the OpenChronicle core modules.

## 📁 Files Overview

### Core Analysis Files
- **`core_refresh_prompt.txt`** - Enhanced prompt for comprehensive architecture analysis
- **`core_method_inventory.md`** - Complete inventory of all methods and functions across core modules
- **`core_refactor_priority.md`** - Prioritized refactoring recommendations based on complexity metrics
- **`architecture_health.md`** - Real-time architecture quality dashboard (NEW)

### Automation Scripts
- **`run_architecture_analysis.ps1`** - PowerShell script for automated metrics collection

### Historical Analysis
- **`3.5/`**, **`3.7/`**, **`4.0/`** - Version-specific analysis results

## 🚀 Quick Start

### 1. Run Automated Analysis (DELETED)
```powershell
# Full analysis (recommended)
.\run_architecture_analysis.ps1

# Skip complexity analysis (faster)
.\run_architecture_analysis.ps1 -SkipComplexity

# Verbose output with detailed dependency info
.\run_architecture_analysis.ps1 -Verbose
```

### 2. Generate Updated Documentation
Use the enhanced `core_refresh_prompt.txt` with Claude to update:
- Method inventory with semantic clustering
- Refactoring priorities with technical debt quantification
- Architecture health dashboard with quality metrics

### 3. Review Results
Check the generated files for:
- **Immediate actionables** - Specific refactoring tasks ready for implementation
- **Risk assessments** - Impact analysis for proposed changes
- **Progress tracking** - Measurable improvements over time

## 🎯 Analysis Capabilities

### Enhanced Intelligence
- **Architectural Pattern Recognition** - Identify design patterns and anti-patterns
- **Cross-Module Dependency Mapping** - Trace dependencies and circular references
- **Semantic Clustering** - Group related functionality using semantic similarity
- **Technical Debt Quantification** - Score and prioritize debt patterns
- **Performance Impact Assessment** - Identify optimization opportunities

### Multi-Dimensional Metrics
- **Complexity Analysis** - Cyclomatic, cognitive, and architectural complexity
- **Coupling/Cohesion** - Quantify module relationships and responsibilities
- **Pattern Consistency** - Measure adherence to design patterns
- **Evolution Tracking** - Monitor growth patterns and complexity trends

### Actionable Outputs
- **Specific Refactoring Plans** - Step-by-step extraction strategies
- **Risk-Assessed Recommendations** - Impact analysis for proposed changes
- **Implementation Roadmaps** - Sequential refactoring plans to minimize disruption
- **Quality Gates** - Automated thresholds for architecture health

## 📊 Output Standards

Each analysis provides:
1. **Immediate Actionables** - Tasks ready for implementation today
2. **Risk Assessment** - "What could go wrong?" analysis
3. **Progress Tracking** - Before/after metrics for measuring improvement
4. **Decision Support** - Data-driven architecture decisions
5. **Quality Trends** - Early warning indicators for architecture drift

## 🔄 Integration with OpenChronicle Workflow

### Daily Usage
- Run quick metrics collection before major changes
- Check architecture health dashboard for quality gates
- Identify immediate refactoring opportunities

### Weekly Reviews
- Analyze complexity trends and dependency changes
- Update refactoring priorities based on new development
- Review progress against quarterly architecture goals

### Monthly Planning
- Comprehensive architecture review with stakeholders
- Update strategic refactoring roadmap
- Assess technical debt accumulation vs. reduction

## 🛠️ Customization

### Adding New Metrics
Edit `run_architecture_analysis.ps1` to include additional pattern detection:
```powershell
$patterns = @{
    "Your Pattern" = "regex_pattern_here"
    # Add more patterns as needed
}
```

### Modifying Quality Gates
Update thresholds in `architecture_health.md`:
```markdown
| Max File Size | Current | 1000 lines | Status |
| Max Methods   | Current | 50/class   | Status |
```

### Custom Reporting
The PowerShell script exports CSV data for integration with external tools:
- Metrics data: `core_metrics_YYYYMMDD_HHMMSS.csv`
- Historical tracking capabilities built-in

## 📚 Best Practices

### Before Major Refactoring
1. Run full analysis to establish baseline metrics
2. Identify all dependencies and potential impact points
3. Create specific, measurable refactoring goals
4. Document expected complexity reduction

### During Development
1. Use quick analysis to validate architectural decisions
2. Monitor complexity growth in real-time
3. Check for new coupling or dependency issues
4. Ensure consistency with established patterns

### After Refactoring
1. Re-run analysis to measure improvement
2. Update architecture health dashboard
3. Validate that complexity targets were met
4. Document lessons learned for future refactoring

## 🔍 Troubleshooting

### Common Issues
- **PowerShell Execution Policy**: Run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
- **Missing Radon**: The script will auto-install if Python is available
- **Large Output**: Use `-SkipComplexity` or `-SkipDependencies` flags for faster runs

### Performance Tips
- Run analysis during low-activity periods for accurate metrics
- Use CSV exports for historical trend analysis
- Combine with git history for change frequency analysis

---

*This analysis suite is designed to be a living diagnostic system for the OpenChronicle architecture. Regular use will help maintain code quality and guide strategic refactoring decisions.*
