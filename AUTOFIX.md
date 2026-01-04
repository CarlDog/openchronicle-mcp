# Auto-Fix and Type Checking Setup

This project uses **markdownlint** for markdown files, **Ruff** for auto-fixing Python code issues, and **mypy** for strict type checking.

## Quick Start

### Run everything (auto-fix + format + type check)

```powershell
.\check-and-fix.ps1
```

Or use VS Code's **Command Palette** (Ctrl+Shift+P):

- Run Task → "Auto-fix and Type Check"

### Individual commands

**Auto-fix markdown files:**

```powershell
npm run lint:md:fix
```

**Auto-fix Python linting issues:**

```powershell
python -m ruff check --fix src tests plugins
```

**Format Python code:**

```powershell
python -m ruff format src tests plugins
```

**Type check with mypy:**

```powershell
python -m mypy src tests plugins --config-file=openchronicle-core/mypy.ini
```

## What Gets Auto-Fixed

**Markdownlint** automatically fixes:

- ✅ Heading style consistency
- ✅ List formatting and indentation
- ✅ Trailing whitespace
- ✅ Multiple blank lines
- ✅ Hard tabs
- ✅ Code fence formatting

**Ruff** automatically fixes:

- ✅ Unused imports
- ✅ Import sorting and organization
- ✅ Code formatting (line length, spacing, etc.)
- ✅ Simple code simplifications
- ✅ Syntax upgrades for newer Python versions
- ✅ Common code smell patterns

## What Requires Manual Fixing

Mypy reports type errors that need manual attention:

- ❌ Missing type annotations
- ❌ Type mismatches
- ❌ Incorrect return types
- ❌ Generic type parameters

## VS Code Integration

### Available Tasks

1. **Auto-fix and Type Check** (Default Build Task: Ctrl+Shift+B)
2. **Markdownlint: Auto-fix**
3. **Markdownlint: Check**
4. **Ruff: Auto-fix**
5. **Ruff: Format**
6. **Mypy: Type Check**

### Configure Auto-fix on Save

Add to `.vscode/settings.json`:

```json
{
  "[python]": {
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.fixAll": "explicit",
      "source.organizeImports": "explicit"
    },
    "editor.defaultFormatter": "charliermarsh.ruff"
  },
  "[markdown]": {
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.fixAll.markdownlint": "explicit"
    }
  }
}
```

## Configuration

- **Markdownlint settings**: `.markdownlint.json`
- **Ruff settings**: `pyproject.toml` → `[tool.ruff]`
- **Mypy settings**: `openchronicle-core/mypy.ini` and `pyproject.toml` → `[tool.mypy]`

## Workflow

1. Write code and documentation
2. Run `.\check-and-fix.ps1` or use the VS Code task (Ctrl+Shift+B)
3. Markdownlint auto-fixes markdown files
4. Ruff auto-fixes Python code issues
5. Mypy reports remaining type errors
6. Fix type errors manually
7. Repeat until all checks pass ✅
