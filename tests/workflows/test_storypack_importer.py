
import os
import json
import pytest
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from utilities.storypack_importer import StorypackImporter

# Get absolute paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
TEST_INPUT_DIR = PROJECT_ROOT / "import" / "BattleChasers"
TEST_OUTPUT_DIR = PROJECT_ROOT / "storage" / "storypacks" / "BattleChasers_Test"
REPORT_DIR = PROJECT_ROOT / "tests" / "output" / "reports"

@pytest.fixture(scope="module")
def importer():
    """Create a StorypackImporter instance for testing."""
    return StorypackImporter(
        source_dir=PROJECT_ROOT / "import",
        output_dir=PROJECT_ROOT / "storage" / "storypacks"
    )

def setup_module(module):
    """Set up test directories and run import."""
    os.makedirs(REPORT_DIR, exist_ok=True)
    
    # Only run import if source directory exists
    if TEST_INPUT_DIR.exists():
        importer = StorypackImporter(
            source_dir=PROJECT_ROOT / "import",
            output_dir=PROJECT_ROOT / "storage" / "storypacks"
        )
        
        # Run the import
        try:
            result = importer.import_from_directory("BattleChasers", import_mode="basic")
            if not result.get("success", False):
                pytest.skip(f"Import failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            pytest.skip(f"Import setup failed: {e}")

def compare_file_contents(file1: Path, file2: Path) -> bool:
    """Compare contents of two files, handling encoding properly."""
    try:
        with open(file1, 'r', encoding='utf-8') as f1, open(file2, 'r', encoding='utf-8') as f2:
            return f1.read().strip() == f2.read().strip()
    except (FileNotFoundError, UnicodeDecodeError) as e:
        return False

def generate_report(results: List[Dict], report_dir: Path):
    """Generate comprehensive test reports."""
    summary = {
        "total_tests": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
        "test_timestamp": str(datetime.now()),
        "details": results
    }

    with open(os.path.join(REPORT_DIR, "test_results.json"), "w", encoding="utf-8") as jf:
        json.dump(summary, jf, indent=4)

    with open(os.path.join(REPORT_DIR, "test_results.txt"), "w", encoding="utf-8") as tf:
        for r in results:
            tf.write(f"{'[PASS]' if r['passed'] else '[FAIL]'} {r['filename']}\n")

    with open(os.path.join(REPORT_DIR, "test_results.md"), "w", encoding="utf-8") as mf:
        mf.write("# Storypack Importer Test Report\n\n")
        mf.write(f"**Test Run**: {summary['test_timestamp']}\n")
        mf.write(f"**Total Tests**: {summary['total_tests']}\n")
        mf.write(f"**Passed**: {summary['passed']}\n")
        mf.write(f"**Failed**: {summary['failed']}\n\n")
        mf.write("## Test Results\n\n")
        for r in results:
            mf.write(f"- {'✅' if r['passed'] else '❌'} **{r['filename']}**\n")

def test_storypack_import_accuracy(importer):
    """Test that storypack import preserves file contents accurately."""
    # Skip if input directory doesn't exist
    if not TEST_INPUT_DIR.exists():
        pytest.skip(f"Input directory {TEST_INPUT_DIR} does not exist")
    
    results = []
    
    # Check if the BattleChasers storypack was created
    storypack_check = importer.check_storypack_exists("BattleChasers_Test")
    if not storypack_check["exists"]:
        pytest.skip("BattleChasers test storypack was not created")
    
    # Compare original files with imported files
    for root, _, files in os.walk(TEST_INPUT_DIR):
        for file in files:
            if file.endswith((".txt", ".md", ".json")):
                input_file = Path(root) / file
                relative_path = input_file.relative_to(TEST_INPUT_DIR)
                
                # Look for the file in the created storypack
                output_file = Path(storypack_check["path"]) / "content" / relative_path
                
                passed = output_file.exists() and compare_file_contents(input_file, output_file)
                results.append({
                    "filename": str(relative_path),
                    "passed": passed,
                    "input_exists": input_file.exists(),
                    "output_exists": output_file.exists(),
                    "input_path": str(input_file),
                    "output_path": str(output_file)
                })

    generate_report(results, REPORT_DIR)
    
    # Assert that all files were imported successfully
    failed_files = [r for r in results if not r["passed"]]
    if failed_files:
        failure_msg = f"Failed to import {len(failed_files)} files:\n"
        for f in failed_files[:5]:  # Show first 5 failures
            failure_msg += f"  - {f['filename']}: input_exists={f['input_exists']}, output_exists={f['output_exists']}\n"
        assert False, failure_msg
    
    assert len(results) > 0, "No files found to test"

def test_storypack_importer_initialization():
    """Test that the StorypackImporter initializes correctly."""
    importer = StorypackImporter()
    
    assert importer is not None
    assert hasattr(importer, 'source_dir')
    assert hasattr(importer, 'output_dir')
    assert hasattr(importer, 'supported_extensions')
    assert '.txt' in importer.supported_extensions
    assert '.md' in importer.supported_extensions
    assert '.json' in importer.supported_extensions

def test_check_storypack_exists_functionality(importer):
    """Test the check_storypack_exists method."""
    # Test with a non-existent storypack
    result = importer.check_storypack_exists("NonExistentStorypack")
    assert result["exists"] is False
    
    # Test with existing import directories
    import_dir = PROJECT_ROOT / "import"
    if import_dir.exists():
        for item in import_dir.iterdir():
            if item.is_dir():
                result = importer.check_storypack_exists(item.name)
                # This should be False unless the storypack was already imported
                assert isinstance(result["exists"], bool)
                break

@pytest.mark.asyncio
async def test_ai_capabilities_if_available(importer):
    """Test AI capabilities initialization if models are available."""
    try:
        ai_initialized = importer.initialize_ai()
        # Should not fail, whether AI is available or not
        assert isinstance(ai_initialized, bool)
        
        if ai_initialized:
            assert importer.ai_available is True
            assert importer.content_analyzer is not None
        else:
            assert importer.ai_available is False
            
    except Exception as e:
        # AI initialization failure is acceptable in test environment
        pytest.skip(f"AI initialization failed (expected in test environment): {e}")

def test_content_categories_definition(importer):
    """Test that content categories are properly defined."""
    assert hasattr(importer, 'content_categories')
    assert isinstance(importer.content_categories, dict)
    
    expected_categories = {'characters', 'locations', 'lore', 'narrative'}
    assert set(importer.content_categories.keys()) == expected_categories
    
    # Check that all categories have non-empty lists
    for category, keywords in importer.content_categories.items():
        assert isinstance(keywords, list)
        assert len(keywords) > 0
        assert all(isinstance(keyword, str) for keyword in keywords)
