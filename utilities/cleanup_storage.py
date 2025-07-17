#!/usr/bin/env python3
"""
OpenChronicle Storage Cleanup Utility
Cleans up old backups, logs, temporary files, and optimizes storage directories.
"""

import os
import sys
import shutil
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add the parent directory to the path so we can import core modules
sys.path.insert(0, str(Path(__file__).parent.parent))

class StorageCleanup:
    """Handles cleanup of OpenChronicle storage directories."""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.root_dir = Path(__file__).parent.parent
        self.storage_dir = self.root_dir / "storage"
        self.config_dir = self.root_dir / "config"
        self.cleaned_files = []
        self.cleaned_size = 0
        
    def scan_for_cleanup(self) -> Dict[str, Any]:
        """Scan for files that can be cleaned up."""
        cleanup_items = {
            "config_backups": [],
            "log_files": [],
            "temp_files": [],
            "old_exports": [],
            "cache_files": [],
            "empty_directories": []
        }
        
        # Find configuration backups
        for backup_file in self.config_dir.glob("*.backup.*"):
            file_stat = backup_file.stat()
            cleanup_items["config_backups"].append({
                "path": backup_file,
                "size": file_stat.st_size,
                "modified": datetime.fromtimestamp(file_stat.st_mtime)
            })
        
        # Find log files
        for log_file in self.root_dir.rglob("*.log"):
            if log_file.is_file():
                file_stat = log_file.stat()
                cleanup_items["log_files"].append({
                    "path": log_file,
                    "size": file_stat.st_size,
                    "modified": datetime.fromtimestamp(file_stat.st_mtime)
                })
        
        # Find temporary files
        temp_patterns = ["*.tmp", "*.temp", "*~", "*.bak"]
        for pattern in temp_patterns:
            for temp_file in self.root_dir.rglob(pattern):
                if temp_file.is_file():
                    file_stat = temp_file.stat()
                    cleanup_items["temp_files"].append({
                        "path": temp_file,
                        "size": file_stat.st_size,
                        "modified": datetime.fromtimestamp(file_stat.st_mtime)
                    })
        
        # Find old exports (older than 30 days)
        cutoff_date = datetime.now() - timedelta(days=30)
        if self.storage_dir.exists():
            for story_dir in self.storage_dir.iterdir():
                if story_dir.is_dir():
                    exports_dir = story_dir / "exports"
                    if exports_dir.exists():
                        for export_file in exports_dir.iterdir():
                            if export_file.is_file():
                                file_stat = export_file.stat()
                                modified_date = datetime.fromtimestamp(file_stat.st_mtime)
                                if modified_date < cutoff_date:
                                    cleanup_items["old_exports"].append({
                                        "path": export_file,
                                        "size": file_stat.st_size,
                                        "modified": modified_date
                                    })
        
        # Find cache files
        cache_patterns = ["__pycache__", "*.pyc", ".pytest_cache", ".coverage"]
        for pattern in cache_patterns:
            for cache_item in self.root_dir.rglob(pattern):
                if cache_item.is_file():
                    file_stat = cache_item.stat()
                    cleanup_items["cache_files"].append({
                        "path": cache_item,
                        "size": file_stat.st_size,
                        "modified": datetime.fromtimestamp(file_stat.st_mtime)
                    })
                elif cache_item.is_dir():
                    # Calculate directory size
                    total_size = sum(f.stat().st_size for f in cache_item.rglob("*") if f.is_file())
                    cleanup_items["cache_files"].append({
                        "path": cache_item,
                        "size": total_size,
                        "modified": datetime.fromtimestamp(cache_item.stat().st_mtime),
                        "is_directory": True
                    })
        
        # Find empty directories
        for root, dirs, files in os.walk(self.storage_dir):
            for dir_name in dirs:
                dir_path = Path(root) / dir_name
                if dir_path.is_dir() and not any(dir_path.iterdir()):
                    cleanup_items["empty_directories"].append({
                        "path": dir_path,
                        "size": 0,
                        "modified": datetime.fromtimestamp(dir_path.stat().st_mtime)
                    })
        
        return cleanup_items
    
    def cleanup_old_backups(self, keep_count: int = 5) -> None:
        """Clean up old configuration backups, keeping only the most recent ones."""
        backup_files = list(self.config_dir.glob("*.backup.*"))
        if len(backup_files) <= keep_count:
            print(f"✅ Only {len(backup_files)} backup files found, keeping all")
            return
        
        # Sort by modification time, newest first
        backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        files_to_remove = backup_files[keep_count:]
        
        print(f"🗑️  Removing {len(files_to_remove)} old backup files (keeping {keep_count} most recent)")
        
        for backup_file in files_to_remove:
            size = backup_file.stat().st_size
            if not self.dry_run:
                backup_file.unlink()
            self.cleaned_files.append(str(backup_file))
            self.cleaned_size += size
            print(f"  - Removed: {backup_file.name} ({self._format_size(size)})")
    
    def cleanup_logs(self, max_age_days: int = 7) -> None:
        """Clean up log files older than specified days."""
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        
        log_files = list(self.root_dir.rglob("*.log"))
        old_logs = [f for f in log_files if datetime.fromtimestamp(f.stat().st_mtime) < cutoff_date]
        
        if not old_logs:
            print("✅ No old log files to clean up")
            return
        
        print(f"🗑️  Removing {len(old_logs)} log files older than {max_age_days} days")
        
        for log_file in old_logs:
            size = log_file.stat().st_size
            if not self.dry_run:
                log_file.unlink()
            self.cleaned_files.append(str(log_file))
            self.cleaned_size += size
            print(f"  - Removed: {log_file.relative_to(self.root_dir)} ({self._format_size(size)})")
    
    def cleanup_temp_files(self) -> None:
        """Clean up temporary files."""
        temp_patterns = ["*.tmp", "*.temp", "*~", "*.bak"]
        temp_files = []
        
        for pattern in temp_patterns:
            temp_files.extend(self.root_dir.rglob(pattern))
        
        if not temp_files:
            print("✅ No temporary files to clean up")
            return
        
        print(f"🗑️  Removing {len(temp_files)} temporary files")
        
        for temp_file in temp_files:
            if temp_file.is_file():
                size = temp_file.stat().st_size
                if not self.dry_run:
                    temp_file.unlink()
                self.cleaned_files.append(str(temp_file))
                self.cleaned_size += size
                print(f"  - Removed: {temp_file.relative_to(self.root_dir)} ({self._format_size(size)})")
    
    def cleanup_cache(self) -> None:
        """Clean up Python cache files and directories."""
        cache_patterns = ["__pycache__", "*.pyc", ".pytest_cache", ".coverage"]
        
        for pattern in cache_patterns:
            cache_items = list(self.root_dir.rglob(pattern))
            
            for cache_item in cache_items:
                if cache_item.is_file():
                    size = cache_item.stat().st_size
                    if not self.dry_run:
                        cache_item.unlink()
                    self.cleaned_files.append(str(cache_item))
                    self.cleaned_size += size
                    print(f"  - Removed file: {cache_item.relative_to(self.root_dir)} ({self._format_size(size)})")
                elif cache_item.is_dir():
                    # Calculate directory size before removal
                    total_size = sum(f.stat().st_size for f in cache_item.rglob("*") if f.is_file())
                    if not self.dry_run:
                        shutil.rmtree(cache_item)
                    self.cleaned_files.append(str(cache_item))
                    self.cleaned_size += total_size
                    print(f"  - Removed directory: {cache_item.relative_to(self.root_dir)} ({self._format_size(total_size)})")
    
    def cleanup_old_exports(self, max_age_days: int = 30) -> None:
        """Clean up old export files."""
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        old_exports = []
        
        if not self.storage_dir.exists():
            print("✅ No storage directory found")
            return
        
        for story_dir in self.storage_dir.iterdir():
            if story_dir.is_dir():
                exports_dir = story_dir / "exports"
                if exports_dir.exists():
                    for export_file in exports_dir.iterdir():
                        if export_file.is_file():
                            modified_date = datetime.fromtimestamp(export_file.stat().st_mtime)
                            if modified_date < cutoff_date:
                                old_exports.append(export_file)
        
        if not old_exports:
            print(f"✅ No export files older than {max_age_days} days")
            return
        
        print(f"🗑️  Removing {len(old_exports)} old export files")
        
        for export_file in old_exports:
            size = export_file.stat().st_size
            if not self.dry_run:
                export_file.unlink()
            self.cleaned_files.append(str(export_file))
            self.cleaned_size += size
            print(f"  - Removed: {export_file.relative_to(self.root_dir)} ({self._format_size(size)})")
    
    def cleanup_empty_directories(self) -> None:
        """Remove empty directories in storage."""
        empty_dirs = []
        
        if not self.storage_dir.exists():
            return
        
        for root, dirs, files in os.walk(self.storage_dir, topdown=False):
            for dir_name in dirs:
                dir_path = Path(root) / dir_name
                if dir_path.is_dir() and not any(dir_path.iterdir()):
                    empty_dirs.append(dir_path)
        
        if not empty_dirs:
            print("✅ No empty directories to clean up")
            return
        
        print(f"🗑️  Removing {len(empty_dirs)} empty directories")
        
        for empty_dir in empty_dirs:
            if not self.dry_run:
                empty_dir.rmdir()
            self.cleaned_files.append(str(empty_dir))
            print(f"  - Removed: {empty_dir.relative_to(self.root_dir)}")
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        if size_bytes == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        i = 0
        while size_bytes >= 1024 and i < len(units) - 1:
            size_bytes /= 1024
            i += 1
        
        return f"{size_bytes:.1f} {units[i]}"
    
    def run_full_cleanup(self) -> None:
        """Run all cleanup operations."""
        print("🧹 Starting OpenChronicle Storage Cleanup")
        print("=" * 50)
        
        if self.dry_run:
            print("🔍 DRY RUN MODE - No files will be actually deleted")
            print()
        
        # Run cleanup operations
        self.cleanup_old_backups()
        self.cleanup_logs()
        self.cleanup_temp_files()
        self.cleanup_cache()
        self.cleanup_old_exports()
        self.cleanup_empty_directories()
        
        # Summary
        print("\n📊 Cleanup Summary:")
        print(f"  🗑️  Files/directories cleaned: {len(self.cleaned_files)}")
        print(f"  💾 Space freed: {self._format_size(self.cleaned_size)}")
        
        if self.dry_run:
            print("\n💡 Run without --dry-run to actually delete files")


def main():
    """Main function with command line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenChronicle Storage Cleanup Utility")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without actually deleting")
    parser.add_argument("--keep-backups", type=int, default=5, help="Number of backup files to keep (default: 5)")
    parser.add_argument("--log-age", type=int, default=7, help="Max age of log files in days (default: 7)")
    parser.add_argument("--export-age", type=int, default=30, help="Max age of export files in days (default: 30)")
    parser.add_argument("--scan-only", action="store_true", help="Only scan and report what could be cleaned")
    
    args = parser.parse_args()
    
    cleanup = StorageCleanup(dry_run=args.dry_run)
    
    if args.scan_only:
        print("🔍 Scanning for cleanup opportunities...")
        cleanup_items = cleanup.scan_for_cleanup()
        
        total_files = 0
        total_size = 0
        
        for category, items in cleanup_items.items():
            if items:
                print(f"\n📁 {category.replace('_', ' ').title()}:")
                for item in items:
                    print(f"  - {item['path'].relative_to(cleanup.root_dir)} ({cleanup._format_size(item['size'])})")
                    total_files += 1
                    total_size += item['size']
        
        print(f"\n📊 Total cleanup potential:")
        print(f"  🗑️  Files/directories: {total_files}")
        print(f"  💾 Space: {cleanup._format_size(total_size)}")
        
    else:
        cleanup.run_full_cleanup()


if __name__ == "__main__":
    main()
