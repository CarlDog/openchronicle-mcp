#!/usr/bin/env python3
"""
OpenChronicle Storypack Import Engine

This module provides the core functionality for importing raw source material
and converting it into structured OpenChronicle storypacks using AI analysis
and template processing.
"""

import os
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, UTC

# Import OpenChronicle infrastructure
from utilities.logging_system import get_logger, log_system_event, log_error, log_info, log_warning
from core.model_manager_compat import ModelManager
from core.content_analysis import ContentAnalysisOrchestrator as ContentAnalyzer


class StorypackImporter:
    """
    Main orchestration class for importing and processing source material
    into OpenChronicle storypacks.
    """
    
    def __init__(self, source_dir: Optional[Path] = None, output_dir: Optional[Path] = None):
        """Initialize the importer with source and output directories."""
        self.logger = get_logger()
        self.root_dir = Path(__file__).parent.parent
        
        # Set default directories
        self.source_dir = source_dir or self.root_dir / "import"
        self.output_dir = output_dir or self.root_dir / "storage" / "storypacks"
        self.templates_dir = self.root_dir / "templates"
        
        # Initialize ModelManager for AI processing
        self.model_manager = None
        self.content_analyzer = None
        self.ai_available = False
        
        # Supported file types
        self.supported_extensions = {'.txt', '.md', '.json'}
        
        # Content type mappings
        self.content_categories = {
            'characters': ['characters', 'people', 'npcs', 'char'],
            'locations': ['locations', 'places', 'settings', 'loc'],
            'lore': ['lore', 'history', 'background', 'world', 'canon'],
            'narrative': ['story', 'plot', 'scenes', 'narrative', 'chapters']
        }
        
        log_system_event("storypack_importer", "Import engine initialized", {
            "source_dir": str(self.source_dir),
            "output_dir": str(self.output_dir),
            "templates_dir": str(self.templates_dir)
        })
    
    def initialize_ai(self) -> bool:
        """Initialize AI capabilities if available."""
        try:
            self.model_manager = ModelManager()
            available_adapters = self.model_manager.get_available_adapters()
            
            if available_adapters:
                # Initialize content analyzer with model manager
                self.content_analyzer = ContentAnalyzer(self.model_manager)
                self.ai_available = True
                log_system_event("storypack_importer", "AI capabilities initialized", {
                    "available_adapters": available_adapters,
                    "ai_enabled": True,
                    "content_analyzer": True
                })
                return True
            else:
                self.logger.warning("No LLM adapters available - falling back to manual processing")
                log_system_event("storypack_importer", "AI unavailable", {
                    "ai_enabled": False,
                    "fallback_mode": "manual"
                })
                return False
        except Exception as e:
            self.logger.error(f"Failed to initialize AI capabilities: {e}")
            log_system_event("storypack_importer", "AI initialization failed", {
                "error": str(e),
                "ai_enabled": False
            })
            return False

    async def test_ai_capabilities(self):
        """Test AI models and their capabilities for import operations."""
        log_info("Testing AI model capabilities for storypack import...")
        
        # Find working models for analysis
        working_models = await self.content_analyzer.find_working_analysis_models()
        
        if not working_models:
            log_warning("No working AI models found! Import will use basic text processing only.")
            print("\n>>> WARNING: No AI models available for enhanced import processing!")
            print("    The import will proceed with basic functionality only.")
            return False
        
        print(f"\n>>> AI Model Discovery Results:")
        print(f"    Found {len(working_models)} working model(s) for analysis")
        
        # Show the top models with their scores
        for i, model in enumerate(working_models[:3], 1):
            status = "[SELECTED]" if i == 1 else "[BACKUP]"
            print(f"    {i}. {model['name']} {status}")
            print(f"       Score: {model['suitability_score']:.1f}/100")
            print(f"       Response time: {model.get('response_time', 0):.2f}s")
            if model.get('suitability_reason'):
                print(f"       Suitability: {model['suitability_reason']}")
            print()
        
        # Test the top model with a sample analysis
        best_model = working_models[0]['name']
        log_info(f"Testing advanced capabilities with model: {best_model}")
        
        test_content = """
        # Chapter 1: The Beginning
        
        Sarah walked through the misty forest, her heart pounding with anticipation. 
        The ancient trees seemed to whisper secrets of the past, and she knew her 
        adventure was just beginning.
        
        **Characters:**
        - Sarah: A young explorer with a brave heart
        - The Forest Spirit: An ancient guardian of the woods
        """
        
        try:
            analysis = await self.content_analyzer.analyze_imported_content(
                test_content, "Chapter 1", "test_analysis"
            )
            
            if analysis and analysis.get('characters'):
                print(f">>> AI Analysis Test: SUCCESS")
                print(f"    Model '{best_model}' successfully analyzed test content")
                print(f"    Detected {len(analysis['characters'])} character(s)")
                print(f"    Analysis depth: {analysis.get('complexity', 'Unknown')}")
                log_info("AI capabilities test passed - enhanced import available")
                return True
            else:
                print(f">>> AI Analysis Test: LIMITED")
                print(f"    Model responded but analysis was incomplete")
                log_warning("AI model available but analysis capabilities limited")
                return True  # Still usable, just limited
                
        except Exception as e:
            print(f">>> AI Analysis Test: FAILED")
            print(f"    Error: {str(e)[:100]}...")
            log_error(f"AI analysis test failed: {e}")
            return False
    
    def scan_import_directory(self) -> Dict[str, Any]:
        """
        Scan the import directory for folders containing story content.
        Check for existing storypacks to avoid duplicates.
        
        Returns:
            Dictionary with import candidates and status information
        """
        if not self.source_dir.exists():
            log_warning(f"Import directory does not exist: {self.source_dir}")
            return {
                "import_candidates": [],
                "existing_storypacks": [],
                "status": "no_import_directory"
            }
        
        import_candidates = []
        existing_storypacks = []
        
        # Scan for directories in the import folder
        for item in self.source_dir.iterdir():
            if item.is_dir():
                candidate_name = item.name
                
                # Check if storypack already exists
                existing_storypack_path = self.output_dir / candidate_name
                
                if existing_storypack_path.exists():
                    # Check if it's a valid storypack (has meta.json)
                    meta_file = existing_storypack_path / "meta.json"
                    if meta_file.exists():
                        existing_storypacks.append({
                            "name": candidate_name,
                            "path": str(existing_storypack_path),
                            "source_path": str(item),
                            "status": "exists_with_meta"
                        })
                        continue
                
                # Scan the candidate directory for content
                discovered_files = self._discover_files_in_directory(item)
                file_count = sum(len(files) for files in discovered_files.values())
                
                if file_count > 0:
                    import_candidates.append({
                        "name": candidate_name,
                        "source_path": str(item),
                        "discovered_files": discovered_files,
                        "file_count": file_count,
                        "status": "ready_for_import"
                    })
        
        result = {
            "import_candidates": import_candidates,
            "existing_storypacks": existing_storypacks,
            "total_candidates": len(import_candidates),
            "total_existing": len(existing_storypacks),
            "status": "scan_complete"
        }
        
        log_system_event("storypack_importer", "Import directory scan completed", {
            "candidates_found": len(import_candidates),
            "existing_storypacks": len(existing_storypacks),
            "import_directory": str(self.source_dir)
        })
        
        return result

    def _discover_files_in_directory(self, directory: Path) -> Dict[str, List[Path]]:
        """
        Discover and categorize files in a specific directory.
        
        Args:
            directory: Directory to scan
            
        Returns:
            Dictionary mapping content categories to lists of file paths
        """
        discovered_files = {category: [] for category in self.content_categories.keys()}
        discovered_files['uncategorized'] = []
        
        # Scan for files recursively
        for file_path in directory.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in self.supported_extensions:
                category = self._categorize_file(file_path)
                discovered_files[category].append(file_path)
        
        return discovered_files

    def check_storypack_exists(self, storypack_name: str) -> Dict[str, Any]:
        """
        Check if a storypack with the given name already exists.
        
        Args:
            storypack_name: Name of the storypack to check
            
        Returns:
            Dictionary with existence status and details
        """
        storypack_path = self.output_dir / storypack_name
        
        if not storypack_path.exists():
            return {
                "exists": False,
                "name": storypack_name,
                "path": str(storypack_path),
                "status": "available"
            }
        
        # Check if it's a valid storypack
        meta_file = storypack_path / "meta.json"
        readme_file = storypack_path / "README.md"
        
        # Count content files
        content_files = []
        for content_dir in ['characters', 'locations', 'lore', 'narrative']:
            content_path = storypack_path / content_dir
            if content_path.exists():
                content_files.extend(list(content_path.glob("*.json")))
        
        return {
            "exists": True,
            "name": storypack_name,
            "path": str(storypack_path),
            "has_meta": meta_file.exists(),
            "has_readme": readme_file.exists(),
            "content_files": len(content_files),
            "status": "exists_complete" if meta_file.exists() else "exists_incomplete"
        }

    def import_from_directory(self, directory_name: str, import_mode: str = "basic") -> Dict[str, Any]:
        """
        Import a specific directory from the import folder as a storypack.
        
        Args:
            directory_name: Name of the directory in the import folder
            import_mode: 'basic' or 'ai'
            
        Returns:
            Dictionary containing import results
        """
        source_path = self.source_dir / directory_name
        
        if not source_path.exists() or not source_path.is_dir():
            return {
                "success": False,
                "error": f"Directory '{directory_name}' not found in import folder",
                "source_path": str(source_path)
            }
        
        # Check if storypack already exists
        existing_check = self.check_storypack_exists(directory_name)
        if existing_check["exists"]:
            return {
                "success": False,
                "error": f"Storypack '{directory_name}' already exists",
                "existing_storypack": existing_check,
                "action_required": "rename_source_or_remove_existing"
            }
        
        # Temporarily set source directory to the specific import folder
        original_source = self.source_dir
        self.source_dir = source_path
        
        try:
            if import_mode == "ai":
                # Run AI import (async method needs special handling)
                return {
                    "success": False,
                    "error": "AI import requires async execution - use run_ai_import_from_directory",
                    "suggested_method": "run_ai_import_from_directory"
                }
            else:
                # Run basic import
                result = self.run_basic_import(directory_name)
                
                if result["success"]:
                    log_system_event("storypack_importer", "Directory import completed", {
                        "directory_name": directory_name,
                        "import_mode": import_mode,
                        "storypack_path": result["storypack_path"]
                    })
                
                return result
                
        finally:
            # Restore original source directory
            self.source_dir = original_source

    async def run_ai_import_from_directory(self, directory_name: str) -> Dict[str, Any]:
        """
        Run AI import for a specific directory from the import folder.
        
        Args:
            directory_name: Name of the directory in the import folder
            
        Returns:
            Dictionary containing import results
        """
        source_path = self.source_dir / directory_name
        
        if not source_path.exists() or not source_path.is_dir():
            return {
                "success": False,
                "error": f"Directory '{directory_name}' not found in import folder",
                "source_path": str(source_path)
            }
        
        # Check if storypack already exists
        existing_check = self.check_storypack_exists(directory_name)
        if existing_check["exists"]:
            return {
                "success": False,
                "error": f"Storypack '{directory_name}' already exists",
                "existing_storypack": existing_check,
                "action_required": "rename_source_or_remove_existing"
            }
        
        # Temporarily set source directory to the specific import folder
        original_source = self.source_dir
        self.source_dir = source_path
        
        try:
            result = await self.run_ai_import(directory_name)
            
            if result["success"]:
                log_system_event("storypack_importer", "AI directory import completed", {
                    "directory_name": directory_name,
                    "storypack_path": result["storypack_path"],
                    "files_processed": result.get("files_processed", 0)
                })
            
            return result
            
        finally:
            # Restore original source directory
            self.source_dir = original_source
        """
        Discover and categorize source files in the staging directory.
        
        Returns:
            Dictionary mapping content categories to lists of file paths
        """
        discovered_files = {category: [] for category in self.content_categories.keys()}
        discovered_files['uncategorized'] = []
        
        if not self.source_dir.exists():
            self.logger.warning(f"Source directory does not exist: {self.source_dir}")
            return discovered_files
        
        # Scan for files
        for file_path in self.source_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in self.supported_extensions:
                category = self._categorize_file(file_path)
                discovered_files[category].append(file_path)
        
        # Log discovery results
        total_files = sum(len(files) for files in discovered_files.values())
        log_system_event("storypack_importer", "File discovery completed", {
            "total_files": total_files,
            "categories": {cat: len(files) for cat, files in discovered_files.items()},
            "source_directory": str(self.source_dir)
        })
        
        return discovered_files
    
    def _categorize_file(self, file_path: Path) -> str:
        """
        Categorize a file based on its path and name.
        
        Args:
            file_path: Path to the file to categorize
            
        Returns:
            Category name or 'uncategorized'
        """
        # Check parent directory name
        parent_name = file_path.parent.name.lower()
        for category, keywords in self.content_categories.items():
            if any(keyword in parent_name for keyword in keywords):
                return category
        
        # Check filename
        filename = file_path.stem.lower()
        for category, keywords in self.content_categories.items():
            if any(keyword in filename for keyword in keywords):
                return category
        
        return 'uncategorized'
    
    def load_templates(self) -> Dict[str, Dict]:
        """
        Load all available templates from the templates directory.
        
        Returns:
            Dictionary mapping template names to template data
        """
        templates = {}
        
        if not self.templates_dir.exists():
            self.logger.error(f"Templates directory does not exist: {self.templates_dir}")
            return templates
        
        for template_file in self.templates_dir.glob("*.json"):
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    template_data = json.load(f)
                    templates[template_file.stem] = template_data
                    self.logger.info(f"Loaded template: {template_file.stem}")
            except Exception as e:
                self.logger.error(f"Failed to load template {template_file}: {e}")
        
        log_system_event("storypack_importer", "Templates loaded", {
            "template_count": len(templates),
            "templates": list(templates.keys())
        })
        
        return templates
    
    def validate_import_readiness(self) -> Tuple[bool, List[str]]:
        """
        Validate that the system is ready for import operations.
        
        Returns:
            Tuple of (is_ready, list_of_issues)
        """
        issues = []
        
        # Check source directory
        if not self.source_dir.exists():
            issues.append(f"Source directory does not exist: {self.source_dir}")
        
        # Check templates directory
        if not self.templates_dir.exists():
            issues.append(f"Templates directory does not exist: {self.templates_dir}")
        
        # Check output directory (create if needed)
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            issues.append(f"Cannot create output directory {self.output_dir}: {e}")
        
        # Check for source files
        if self.source_dir.exists():
            source_files = list(self.source_dir.rglob("*"))
            if not any(f.is_file() and f.suffix.lower() in self.supported_extensions 
                      for f in source_files):
                issues.append("No supported source files found in staging directory")
        
        # Check for templates
        if self.templates_dir.exists():
            template_files = list(self.templates_dir.glob("*.json"))
            if not template_files:
                issues.append("No template files found in templates directory")
        
        is_ready = len(issues) == 0
        
        log_system_event("storypack_importer", "Import readiness validation", {
            "is_ready": is_ready,
            "issues_count": len(issues),
            "issues": issues
        })
        
        return is_ready, issues
    
    def create_storypack_structure(self, storypack_name: str, discovered_content: Optional[Dict] = None) -> Path:
        """
        Create the optimal directory structure for a new storypack.
        
        Structure:
        - Root files: meta.json, README.md, style_guide.json (optional), instructions.json (optional)
        - Content directories: characters/, locations/, lore/, narrative/ (created based on discovered content)
        - Individual files within each content directory for maximum flexibility
        
        Args:
            storypack_name: Name of the storypack to create
            discovered_content: Optional dict of discovered content categories
            
        Returns:
            Path to the created storypack directory
        """
        storypack_path = self.output_dir / storypack_name
        
        # Create main directory
        storypack_path.mkdir(parents=True, exist_ok=True)
        
        # Content directories - create based on discovered content and core categories
        content_dirs = ['characters', 'locations', 'lore', 'narrative']
        created_dirs = []
        
        for category in content_dirs:
            dir_path = storypack_path / category
            
            # Always create core directories (characters, locations, lore)
            # Create narrative only if we have content for it
            if category in ['characters', 'locations', 'lore']:
                dir_path.mkdir(exist_ok=True)
                created_dirs.append(category)
                
                # Add helpful README for empty directories
                if not discovered_content or category not in discovered_content or not discovered_content[category]:
                    self._create_directory_readme(dir_path, category)
                    
            elif discovered_content and category in discovered_content and discovered_content[category]:
                dir_path.mkdir(exist_ok=True)
                created_dirs.append(category)
        
        # Create the main storypack README
        self._create_storypack_readme(storypack_path, created_dirs)
        
        log_system_event("storypack_importer", "Storypack structure created", {
            "storypack_name": storypack_name,
            "storypack_path": str(storypack_path),
            "subdirectories": created_dirs,
            "structure_type": "optimized_individual_files"
        })
        
        return storypack_path
    
    def get_import_summary(self) -> Dict[str, Any]:
        """
        Generate a summary of the current import environment.
        
        Returns:
            Dictionary containing import environment information
        """
        # Discover files
        discovered_files = self.discover_source_files()
        
        # Load templates
        templates = self.load_templates()
        
        # Check readiness
        is_ready, issues = self.validate_import_readiness()
        
        summary = {
            "timestamp": datetime.now(UTC).isoformat(),
            "source_directory": str(self.source_dir),
            "output_directory": str(self.output_dir),
            "templates_directory": str(self.templates_dir),
            "ai_available": self.ai_available,
            "discovered_files": {
                cat: [str(f) for f in files] 
                for cat, files in discovered_files.items()
            },
            "available_templates": list(templates.keys()),
            "import_ready": is_ready,
            "validation_issues": issues,
            "supported_extensions": list(self.supported_extensions)
        }
        
        return summary
    
    def run_basic_import(self, storypack_name: str) -> Dict[str, Any]:
        """
        Run a basic import process without AI enhancement.
        
        Args:
            storypack_name: Name of the storypack to create
            
        Returns:
            Dictionary containing import results
        """
        self.logger.info(f"Starting basic import for storypack: {storypack_name}")
        
        # Validate readiness
        is_ready, issues = self.validate_import_readiness()
        if not is_ready:
            error_msg = f"Import validation failed: {issues}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg, "issues": issues}
        
        # Discover source files
        discovered_files = self.discover_source_files()
        
        # Load templates
        templates = self.load_templates()
        
        # Create storypack structure
        storypack_path = self.create_storypack_structure(storypack_name, discovered_files)
        
        # Create basic meta.json from template
        if 'meta_template' in templates:
            meta_data = self._create_basic_meta(storypack_name, templates['meta_template'])
            meta_path = storypack_path / "meta.json"
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta_data, f, indent=2)
            self.logger.info(f"Created meta.json for {storypack_name}")
        
        result = {
            "success": True,
            "storypack_name": storypack_name,
            "storypack_path": str(storypack_path),
            "discovered_files": {
                cat: [str(f) for f in files] 
                for cat, files in discovered_files.items()
            },
            "templates_used": list(templates.keys()),
            "created_files": ["meta.json"]
        }
        
        log_system_event("storypack_importer", "Basic import completed", result)
        
        return result
    
    def _create_basic_meta(self, storypack_name: str, meta_template: Dict) -> Dict:
        """Create basic metadata from template."""
        # Start with template structure
        meta_data = meta_template.copy()
        
        # Remove template-specific fields
        if 'template_info' in meta_data:
            del meta_data['template_info']
        
        # Set basic required fields
        meta_data.update({
            "name": storypack_name,
            "title": storypack_name.replace('_', ' ').title(),
            "version": "1.0.0",
            "description": f"Imported storypack: {storypack_name}",
            "author": "OpenChronicle Import Tool",
            "created": datetime.now(UTC).strftime('%Y-%m-%d'),
            "last_modified": datetime.now(UTC).strftime('%Y-%m-%d')
        })
        
        # Clean up optional fields marked for deletion
        self._clean_optional_fields(meta_data)
        
        return meta_data
    
    def _clean_optional_fields(self, data: Any) -> None:
        """Recursively remove fields marked with '_optional': True."""
        if isinstance(data, dict):
            keys_to_remove = []
            for key, value in data.items():
                if isinstance(value, dict):
                    if value.get('_optional') is True:
                        keys_to_remove.append(key)
                    else:
                        # Remove just the _optional marker if it exists
                        if '_optional' in value:
                            del value['_optional']
                        self._clean_optional_fields(value)
                elif isinstance(value, list):
                    for item in value:
                        self._clean_optional_fields(item)
            
            # Remove optional fields
            for key in keys_to_remove:
                del data[key]
        elif isinstance(data, list):
            for item in data:
                self._clean_optional_fields(item)

    async def analyze_content_with_ai(self, file_path: Path, content: str) -> Dict[str, Any]:
        """Analyze content using AI-powered content analyzer."""
        try:
            log_system_event("storypack_importer", "AI content analysis started", {
                "file": file_path.name,
                "content_length": len(content)
            })
            
            if not self.ai_available or not self.content_analyzer:
                raise Exception("AI capabilities not available")
            
            # First, determine content category
            category_result = await self.content_analyzer.analyze_content_category(content)
            primary_category = category_result.get("primary_category", "unknown")
            
            # Extract specific data based on category
            extracted_data = {}
            if primary_category == "character":
                extracted_data = await self.content_analyzer.extract_character_data(content)
            elif primary_category == "location":
                extracted_data = await self.content_analyzer.extract_location_data(content)
            elif primary_category == "lore":
                extracted_data = await self.content_analyzer.extract_lore_data(content)
            else:
                # For other content types, use general analysis
                extracted_data = {"content": content, "type": primary_category}
            
            # Combine category analysis with extracted data
            result = {
                "file_path": str(file_path),
                "category_analysis": category_result,
                "extracted_data": extracted_data,
                "processing_timestamp": datetime.now(UTC).isoformat(),
                "source_content_length": len(content),
                "ai_processing": True
            }
            
            log_system_event("storypack_importer", "AI content analysis completed", {
                "file": file_path.name,
                "category": primary_category,
                "confidence": extracted_data.get('confidence', 0.0),
                "success": True
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"AI content analysis failed for {file_path.name}: {e}")
            log_system_event("storypack_importer", "AI content analysis failed", {
                "file": file_path.name,
                "error": str(e),
                "fallback_used": True
            })
            
            return {
                "file_path": str(file_path),
                "error": str(e),
                "fallback_content": content,
                "processing_timestamp": datetime.now(UTC).isoformat(),
                "ai_processing": False
            }

    async def run_ai_import(self, storypack_name: str) -> Dict[str, Any]:
        """Run a full AI-powered import process."""
        try:
            log_system_event("storypack_importer", "AI import process started", {
                "storypack_name": storypack_name
            })
            
            # Validate readiness
            is_ready, issues = self.validate_import_readiness()
            if not is_ready:
                return {
                    "success": False,
                    "error": "Import validation failed",
                    "issues": issues
                }
            
            # Initialize AI if not already done
            if not self.ai_available:
                if not self.initialize_ai():
                    return {
                        "success": False,
                        "error": "AI initialization failed"
                    }
            
            # Discover and analyze files
            discovered_files = self.discover_source_files()
            analysis_results = []
            
            for category, files in discovered_files.items():
                for file_path in files:
                    try:
                        content = file_path.read_text(encoding='utf-8')
                        analysis = await self.analyze_content_with_ai(file_path, content)
                        analysis_results.append(analysis)
                    except Exception as e:
                        self.logger.error(f"Failed to process {file_path}: {e}")
            
            # Generate metadata for the entire storypack
            all_content = []
            for result in analysis_results:
                if "fallback_content" in result:
                    all_content.append(result["fallback_content"])
                elif "extracted_data" in result and "content" in result["extracted_data"]:
                    all_content.append(result["extracted_data"]["content"])
            
            metadata = {}
            if self.content_analyzer:
                metadata = await self.content_analyzer.generate_import_metadata(all_content, storypack_name)
            
            # Create storypack structure
            storypack_path = self.create_storypack_structure(storypack_name, {"discovered": True})
            
            # Save analysis results
            analysis_file = storypack_path / "import_analysis.json"
            analysis_data = {
                "storypack_name": storypack_name,
                "import_timestamp": datetime.now(UTC).isoformat(),
                "metadata": metadata,
                "analysis_results": analysis_results,
                "processing_summary": {
                    "total_files": len(analysis_results),
                    "ai_processed": len([r for r in analysis_results if r.get("ai_processing", False)]),
                    "categories": list(set(r.get("category_analysis", {}).get("primary_category", "unknown") 
                                         for r in analysis_results))
                }
            }
            
            with analysis_file.open('w', encoding='utf-8') as f:
                json.dump(analysis_data, f, indent=2)
            
            log_system_event("storypack_importer", "AI import process completed", {
                "storypack_name": storypack_name,
                "files_processed": len(analysis_results),
                "output_path": str(storypack_path)
            })
            
            return {
                "success": True,
                "storypack_name": storypack_name,
                "storypack_path": str(storypack_path),
                "files_processed": len(analysis_results),
                "analysis_results": analysis_results,
                "metadata": metadata
            }
            
        except Exception as e:
            self.logger.error(f"AI import process failed: {e}")
            log_system_event("storypack_importer", "AI import process failed", {
                "storypack_name": storypack_name,
                "error": str(e)
            })
            
            return {
                "success": False,
                "error": str(e),
                "storypack_name": storypack_name
            }

    def _create_directory_readme(self, dir_path: Path, category: str) -> None:
        """
        Create a helpful README file for empty content directories.
        
        Args:
            dir_path: Path to the directory
            category: Category name for the directory
        """
        readme_content = f"""# {category.title()}

This directory contains {category} for your storypack.

## File Organization
- **Individual files**: Create separate JSON files for each {category[:-1] if category.endswith('s') else category}
- **Naming**: Use descriptive names like `sarah_chen.json`, `crystal_city.json`, or `magic_system.json`
- **Templates**: Use the appropriate OpenChronicle template for consistency

## Content Guidelines
"""
        
        if category == "characters":
            readme_content += """- Each character should have their own JSON file
- Include personality, background, relationships, and development arcs
- Use the character_template.json structure for consistency
- Example: `protagonist.json`, `villain.json`, `wise_mentor.json`
"""
        elif category == "locations":
            readme_content += """- Create individual files for significant places
- Include atmosphere, notable features, and story connections
- Use the location_template.json structure for consistency
- Example: `tavern.json`, `castle_throne_room.json`, `mysterious_forest.json`
"""
        elif category == "lore":
            readme_content += """- Organize world-building elements into logical files
- Include magic systems, histories, cultures, and significant items
- Use world_template.json or content_template.json structures
- Example: `magic_system.json`, `ancient_history.json`, `legendary_weapons.json`
- **Items**: Legendary weapons, artifacts, and significant objects belong here
"""
        elif category == "narrative":
            readme_content += """- Structure your story elements and plot progression
- Include acts, scenes, chapters, and plot threads
- Use narrative_template.json and scene_template.json structures
- Example: `main_plot.json`, `character_arcs.json`, `act_1_setup.json`
"""
        
        readme_content += """
## Getting Started
1. Create your first file using the appropriate template
2. Fill in the required fields and customize as needed
3. Add more files as your content grows

For more information, see the main storypack README.md file.
"""
        
        readme_path = dir_path / "README.md"
        readme_path.write_text(readme_content, encoding='utf-8')
        
    def _create_storypack_readme(self, storypack_path: Path, created_dirs: List[str]) -> None:
        """
        Create the main README file for the storypack.
        
        Args:
            storypack_path: Path to the storypack directory
            created_dirs: List of directories that were created
        """
        storypack_name = storypack_path.name
        
        readme_content = f"""# {storypack_name}

Welcome to your OpenChronicle storypack! This collection contains all the elements needed to build and run narrative experiences.

## Storypack Structure

### Root Files
- **meta.json**: Core storypack metadata and configuration
- **README.md**: This documentation file
- **style_guide.json** *(optional)*: Writing style and tone guidelines
- **instructions.json** *(optional)*: AI behavior instructions
- **content.json** *(optional)*: Generated content and item catalogs

### Content Directories
"""
        
        for directory in created_dirs:
            if directory == "characters":
                readme_content += """
#### characters/
Individual character files with personalities, backgrounds, and development arcs.
- **Purpose**: Store each character in a separate JSON file
- **Template**: character_template.json
- **Examples**: `hero.json`, `villain.json`, `wise_mentor.json`
- **Content**: Personality traits, backstory, relationships, character development
"""
            elif directory == "locations":
                readme_content += """
#### locations/
Individual location files for places in your world.
- **Purpose**: Store each significant location in a separate JSON file  
- **Template**: location_template.json
- **Examples**: `tavern.json`, `castle.json`, `mysterious_forest.json`
- **Content**: Atmosphere, notable features, story connections
"""
            elif directory == "lore":
                readme_content += """
#### lore/
World-building elements including magic systems, histories, cultures, and items.
- **Purpose**: Store world-building elements in organized files
- **Templates**: world_template.json, content_template.json
- **Examples**: `magic_system.json`, `ancient_history.json`, `legendary_weapons.json`
- **Content**: Magic systems, historical events, cultures, significant items
- **Items**: This is where legendary weapons, artifacts, and important objects belong
"""
            elif directory == "narrative":
                readme_content += """
#### narrative/
Story structure elements including acts, scenes, and plot progression.
- **Purpose**: Organize story structure and plot elements
- **Templates**: narrative_template.json, scene_template.json
- **Examples**: `main_plot.json`, `character_arcs.json`, `act_1_setup.json`
- **Content**: Plot progression, story acts, character development arcs
"""
        
        readme_content += """
## File Organization Principles

### Individual Files Approach
- **Flexibility**: Each element (character, location, lore item) gets its own file
- **Discoverability**: Easy to browse and find content in file explorers
- **Version Control**: Git-friendly with clean diffs and collaboration
- **Modularity**: Edit one element without affecting others

### Content Categories
- **Characters**: People, beings, and entities in your story
- **Locations**: Places, buildings, and geographical areas
- **Lore**: World-building elements, items, magic systems, and background information
- **Narrative**: Story structure, plot progression, and scene organization

### Where Things Go
- **Legendary Items**: Place in `lore/` (e.g., `lore/excalibur.json`)
- **Personal Items**: Reference in character files' `personal_items` array
- **Location Items**: Include in location files' `notable_features`
- **Plot Elements**: Organize in `narrative/` directory

## Getting Started

1. **Review Templates**: Check the `templates/` directory for JSON structures
2. **Start Small**: Begin with a few characters and locations
3. **Expand Gradually**: Add lore and narrative elements as your world grows
4. **Stay Organized**: Use descriptive filenames and consistent structures

## OpenChronicle Integration

This storypack is designed to work seamlessly with OpenChronicle's narrative AI engine:
- **Templates**: Follow OpenChronicle template structures for compatibility
- **Content Analysis**: AI can analyze and enhance your content
- **Story Generation**: Structured content enables rich narrative experiences
- **Memory Integration**: Characters and lore integrate with AI memory systems

## Need Help?

- **Templates**: See `templates/` directory for JSON structures
- **Documentation**: Check OpenChronicle documentation
- **Examples**: Look at existing storypacks for inspiration

Happy storytelling!
"""
        
        readme_path = storypack_path / "README.md"
        readme_path.write_text(readme_content, encoding='utf-8')
        
        log_system_event("storypack_importer", "Documentation created", {
            "storypack_name": storypack_name,
            "readme_created": str(readme_path),
            "directories_documented": created_dirs
        })
    
    def discover_source_files(self) -> Dict[str, List[Path]]:
        """
        Discover and categorize source files in the current source directory.
        This is a wrapper around _discover_files_in_directory for backwards compatibility.
        
        Returns:
            Dictionary mapping content categories to lists of file paths
        """
        if not self.source_dir.exists():
            self.logger.warning(f"Source directory does not exist: {self.source_dir}")
            return {category: [] for category in self.content_categories.keys()}
        
        discovered_files = self._discover_files_in_directory(self.source_dir)
        
        # Log discovery results
        total_files = sum(len(files) for files in discovered_files.values())
        log_system_event("storypack_importer", "File discovery completed", {
            "total_files": total_files,
            "categories": {cat: len(files) for cat, files in discovered_files.items()},
            "source_directory": str(self.source_dir)
        })
        
        return discovered_files
    

# Convenience function for quick testing
def quick_import_test(storypack_name: str = "test_import") -> Dict[str, Any]:
    """Quick test function for import functionality."""
    importer = StorypackImporter()
    importer.initialize_ai()
    return importer.run_basic_import(storypack_name)


def cli_main():
    """
    Command-line interface for storypack importing.
    
    Usage:
        python -m utilities.storypack_importer <source_directory> <storypack_name> [options]
        
    Examples:
        # Basic import
        python -m utilities.storypack_importer "C:/my_story" "fantasy_realm" --basic
        
        # AI-powered import  
        python -m utilities.storypack_importer "C:/my_story" "fantasy_realm" --ai
        
        # Preview mode
        python -m utilities.storypack_importer "C:/my_story" "preview" --preview
    """
    import argparse
    import sys
    import asyncio
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="Import story content into OpenChronicle storypacks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Basic file import:
    python -m utilities.storypack_importer --source "C:/my_story" --name "fantasy_realm" --basic
    
  AI-powered analysis:
    python -m utilities.storypack_importer --source "C:/my_story" --name "fantasy_realm" --ai
    
  Preview mode:
    python -m utilities.storypack_importer --source "C:/my_story" --name "preview" --preview
    
  Scan import directory:
    python -m utilities.storypack_importer --scan
    
  Import from import directory:
    python -m utilities.storypack_importer --import-dir "FantasyAdventure" --basic
    python -m utilities.storypack_importer --import-dir "BattleChasers" --ai
        """
    )
    
    # Source and target specifications
    parser.add_argument("--source", "-s", 
                       help="Source directory containing story files")
    parser.add_argument("--name", "-n",
                       help="Name for the new storypack")
    parser.add_argument("--import-dir", "-d",
                       help="Import a specific directory from the import folder")
    
    # Import mode options
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--basic", action="store_true",
                           help="Basic import (file discovery only)")
    mode_group.add_argument("--ai", action="store_true", 
                           help="AI-powered import (full content analysis)")
    mode_group.add_argument("--preview", action="store_true",
                           help="Preview mode (show what would be imported)")
    mode_group.add_argument("--scan", action="store_true",
                           help="Scan import directory for available imports")
    
    # Optional parameters
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be done without executing")
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.scan:
        # Scan mode doesn't need any other arguments
        pass
    elif args.import_dir:
        # Import directory mode - directory name is provided via --import-dir
        if not (args.basic or args.ai):
            print("Error: --import-dir requires either --basic or --ai")
            sys.exit(1)
    else:
        # Direct import modes need source directory and name
        if not args.source:
            print("Error: --source directory required for direct import modes")
            sys.exit(1)
        if not args.name:
            print("Error: --name required for direct import modes")
            sys.exit(1)
            
        source_path = Path(args.source)
        if not source_path.exists():
            print(f"Error: Source directory '{args.source}' does not exist")
            sys.exit(1)
        
        if not source_path.is_dir():
            print(f"Error: '{args.source}' is not a directory")
            sys.exit(1)
    
    # Run the import
    try:
        asyncio.run(_run_cli_import(args))
    except KeyboardInterrupt:
        print("\nImport cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error during import: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


async def _run_cli_import(args):
    """Execute the CLI storypack import operation"""
    
    print("OpenChronicle Storypack Importer")
    print("=" * 40)
    
    if args.scan:
        print("Mode: SCAN (discover available imports)")
        print()
        
        # Initialize importer with default import directory
        print("Scanning import directory...")
        importer = StorypackImporter()
        scan_result = importer.scan_import_directory()
        
        if scan_result["status"] == "no_import_directory":
            print("❌ Import directory does not exist")
            print(f"Expected location: {importer.source_dir}")
            print("Create the 'import' directory and add story folders to it.")
            return
        
        print(f"Found {scan_result['total_candidates']} import candidates")
        print(f"Found {scan_result['total_existing']} existing storypacks")
        print()
        
        if scan_result["import_candidates"]:
            print("📁 AVAILABLE FOR IMPORT:")
            for candidate in scan_result["import_candidates"]:
                print(f"  ✓ {candidate['name']} ({candidate['file_count']} files)")
                print(f"    Path: {candidate['source_path']}")
        else:
            print("📁 No import candidates found")
        
        if scan_result["existing_storypacks"]:
            print("\n⚠️  ALREADY IMPORTED (skipped):")
            for existing in scan_result["existing_storypacks"]:
                print(f"  ⚠️  {existing['name']} (already exists)")
                print(f"    Storypack: {existing['path']}")
                print(f"    Source: {existing['source_path']}")
        
        print("\nTo import a candidate:")
        print("  python -m utilities.storypack_importer --import-dir \"folder_name\" --basic")
        print("  python -m utilities.storypack_importer --import-dir \"folder_name\" --ai")
        
        return
    
    elif args.import_dir:
        print(f"Mode: IMPORT DIRECTORY")
        print(f"Directory: {args.import_dir}")
        
        if args.basic:
            print("Import Mode: BASIC")
        elif args.ai:
            print("Import Mode: AI-POWERED")
        else:
            print("Error: --import-dir requires either --basic or --ai")
            sys.exit(1)
        
        print()
        
        # Initialize importer
        print("Initializing importer...")
        importer = StorypackImporter()
        
        # Check if directory exists in import folder
        import_path = importer.source_dir / args.import_dir
        if not import_path.exists():
            print(f"❌ Directory '{args.import_dir}' not found in import folder")
            print(f"Expected location: {import_path}")
            # Show available directories
            scan_result = importer.scan_import_directory()
            if scan_result["import_candidates"]:
                print(f"\nAvailable directories:")
                for candidate in scan_result["import_candidates"]:
                    print(f"  - {candidate['name']}")
            sys.exit(1)
        
        # Run the import
        if args.basic:
            print("Starting basic import from directory...")
            result = importer.import_from_directory(args.import_dir, "basic")
        else:  # args.ai
            print("Starting AI import from directory...")
            result = await importer.run_ai_import_from_directory(args.import_dir)
        
        if result["success"]:
            print(f"✅ Import completed successfully!")
            print(f"  Storypack: {result['storypack_path']}")
            if "files_processed" in result:
                print(f"  Files processed: {result['files_processed']}")
        else:
            print(f"❌ Import failed: {result.get('error', 'Unknown error')}")
            if "existing_storypack" in result:
                existing = result["existing_storypack"]
                print(f"  Existing storypack found at: {existing['path']}")
                print(f"  Status: {existing['status']}")
            sys.exit(1)
        
        return
    
    # Direct import modes (basic, ai, preview) - handle as before
    print(f"Source: {args.source}")
    print(f"Storypack: {args.name}")
    
    if args.preview:
        print("Mode: PREVIEW (no files will be created)")
    elif args.basic:
        print("Mode: BASIC (file discovery only)")
    elif args.ai:
        print("Mode: AI-POWERED (full content analysis)")
    
    print()
    
    # Initialize the importer with source directory
    print("Initializing importer...")
    source_path = Path(args.source).resolve()
    importer = StorypackImporter(source_path)
    
    if args.preview:
        # Preview mode - discover files and show what would be imported
        print("Discovering files...")
        discovered_files = importer.discover_source_files()
        
        print(f"\nDiscovered files by category:")
        total_files = 0
        for category, files in discovered_files.items():
            if files:
                print(f"\n{category.upper()} ({len(files)} files):")
                for file_path in files:
                    rel_path = os.path.relpath(file_path, args.source)
                    print(f"  - {rel_path}")
                total_files += len(files)
        
        print(f"\nTotal files to import: {total_files}")
        
        if args.ai:
            print("\nAI Analysis would be performed on all discovered files")
            print("AI capabilities:")
            try:
                ai_ready = importer.test_ai_capabilities()
                if ai_ready:
                    print("  ✓ Content categorization")
                    print("  ✓ Character extraction")
                    print("  ✓ Location extraction") 
                    print("  ✓ Lore extraction")
                    print("  ✓ Metadata generation")
                else:
                    print("  ✗ AI analysis not available (no working models)")
            except Exception as e:
                print(f"  ✗ AI unavailable: {e}")
        
    elif args.basic:
        # Basic import
        print("Starting basic import...")
        if args.dry_run:
            print("DRY RUN: No files will be created")
            return
        
        # Validate readiness
        ready, issues = importer.validate_import_readiness()
        if not ready:
            print("Import readiness check failed:")
            for issue in issues:
                print(f"  - {issue}")
            sys.exit(1)
        
        result = importer.run_basic_import(args.name)
        
        if result["success"]:
            print(f"✓ Basic import completed successfully!")
            print(f"  Storypack: {result['storypack_path']}")
            print(f"  Templates used: {len(result.get('templates_used', []))}")
            discovered_files = result.get('discovered_files', {})
            total_files = sum(len(files) for files in discovered_files.values())
            print(f"  Source files discovered: {total_files}")
        else:
            print(f"✗ Import failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
    
    elif args.ai:
        # AI-powered import
        print("Starting AI-powered import...")
        print("This may take several minutes depending on content volume...")
        
        if args.dry_run:
            print("DRY RUN: No files will be created")
            return
        
        # Validate readiness
        ready, issues = importer.validate_import_readiness()
        if not ready:
            print("Import readiness check failed:")
            for issue in issues:
                print(f"  - {issue}")
            sys.exit(1)
        
        result = await importer.run_ai_import(args.name)
        
        if result["success"]:
            print(f"✓ AI import completed successfully!")
            print(f"  Storypack: {result['storypack_path']}")
            print(f"  Files processed: {result['files_processed']}")
            metadata_confidence = result.get('metadata', {}).get('confidence', 0)
            print(f"  Analysis confidence: {metadata_confidence:.1%}")
            print(f"  Detailed analysis: import_analysis.json")
        else:
            print(f"✗ Import failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
    
    print("\nImport complete!")


if __name__ == "__main__":
    cli_main()
