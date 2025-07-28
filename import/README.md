# Import Directory

This directory serves as a staging area for importing external story content into OpenChronicle storypacks.

## Purpose

The `import/` directory provides a safe, organized way to prepare story content for import into OpenChronicle's storypack system. Instead of directly importing from scattered locations, users can organize their content here first, allowing the import system to scan, validate, and prevent duplicate imports.

## How It Works

1. **Content Staging**: Place story content folders in this directory
2. **Scanning**: Use `--scan` mode to discover available imports  
3. **Import**: Use `--import-dir` mode to safely import content
4. **Duplicate Prevention**: System checks for existing storypacks and warns about conflicts

## Usage Commands

### Scan for Available Imports
```bash
python -m utilities.storypack_importer --scan
```

### Import a Specific Directory (Basic Mode)
```bash
python -m utilities.storypack_importer --import-dir "DirectoryName" --basic
```

### Import with AI Analysis
```bash
python -m utilities.storypack_importer --import-dir "DirectoryName" --ai
```

## Directory Structure

```
import/
├── README.md               # This file (always kept in git)
├── YourStoryPack1/        # Your story content folder
│   ├── characters.txt
│   ├── plot.md
│   └── world_info.txt
├── AnotherStory/          # Another story to import
│   ├── character_data/
│   ├── narrative.txt
│   └── settings.json
└── ThirdStory/            # Yet another story
    └── story_files...
```

## Import Process

1. **Organize Content**: Create a folder for each story you want to import
2. **Add Files**: Place all related story files in the appropriate folder
3. **Scan**: Run the scan command to see what's available for import
4. **Import**: Choose basic or AI-powered import for each story
5. **Validation**: System prevents overwrites of existing storypacks

## Content Organization Tips

- **One folder per story**: Each subfolder becomes one storypack
- **Meaningful names**: Folder names become storypack names
- **Mixed file types**: Include .txt, .md, .json, or any text-based files
- **Nested organization**: Subfolders are fine (characters/, locations/, etc.)

## Safety Features

- **Non-destructive**: Never overwrites existing storypacks
- **Preview mode**: See what would be imported before committing
- **Clear feedback**: Shows which stories are available vs. already imported
- **Flexible imports**: Choose basic file organization or AI-powered analysis

## Git Behavior

- **Contents ignored**: All subdirectories and files are ignored by git
- **README preserved**: This documentation file is always tracked
- **Clean workspace**: Import staging doesn't clutter the repository

## Example Workflow

1. Download or copy story content to `import/MyEpicTale/`
2. Run `python -m utilities.storypack_importer --scan`
3. See "MyEpicTale" listed as available for import
4. Run `python -m utilities.storypack_importer --import-dir "MyEpicTale" --basic`
5. Story is imported to `storage/storypacks/MyEpicTale/`
6. Future scans show "MyEpicTale" as already imported (safe from overwrites)

---

**Note**: This import system replaces the old `analysis/import_staging` approach, providing better organization and duplicate protection.
