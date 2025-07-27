#!/usr/bin/env python3
import tempfile
import shutil
from pathlib import Path
from utilities.storypack_importer import StorypackImporter

# Create a temporary directory
tmp_dir = Path(tempfile.mkdtemp())
print(f"Using temp directory: {tmp_dir}")

try:
    # Create importer
    importer = StorypackImporter(tmp_dir)
    
    # Test structure creation
    result = importer.create_storypack_structure('test_structure')
    print(f"Created storypack at: {result}")
    
    # Show contents
    print("\nStorypack contents:")
    for item in sorted(result.iterdir()):
        if item.is_dir():
            print(f"  📁 {item.name}/")
            # Show directory contents
            for subitem in sorted(item.iterdir()):
                print(f"     📄 {subitem.name}")
        else:
            print(f"  📄 {item.name}")
    
    print("\n✅ Structure creation test passed!")
    
finally:
    # Cleanup
    shutil.rmtree(tmp_dir)
    print(f"Cleaned up temp directory: {tmp_dir}")
