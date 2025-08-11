#!/usr/bin/env python3
"""
OpenChronicle Storypack Orchestrator

Main coordination class for the modular storypack import system.
Follows SOLID principles with dependency injection and clean orchestration.
"""

from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

from openchronicle.shared.logging_system import get_logger
from openchronicle.shared.logging_system import log_error
from openchronicle.shared.logging_system import log_info
from openchronicle.shared.logging_system import log_system_event
from openchronicle.shared.logging_system import log_warning

from .generators import OutputFormatter
from .generators import StorypackBuilder
from .generators import TemplateEngine
from .interfaces import ContentFile
from .interfaces import IAIProcessor
from .interfaces import IContentClassifier
from .interfaces import IContentParser
from .interfaces import IMetadataExtractor
from .interfaces import ImportContext
from .interfaces import ImportResult
from .interfaces import IOutputFormatter
from .interfaces import IStorypackBuilder
from .interfaces import IStructureAnalyzer
from .interfaces import ITemplateEngine
from .interfaces import IValidationEngine
from .parsers import ContentParser
from .parsers import MetadataExtractor
from .parsers import StructureAnalyzer
from .processors import AIProcessor
from .processors import ContentClassifier
from .processors import ValidationEngine


class StorypackOrchestrator:
    """
    Main orchestrator for storypack import operations.
    Coordinates all components following SOLID principles.
    """

    def __init__(
        self,
        content_parser: IContentParser | None = None,
        metadata_extractor: IMetadataExtractor | None = None,
        structure_analyzer: IStructureAnalyzer | None = None,
        ai_processor: IAIProcessor | None = None,
        content_classifier: IContentClassifier | None = None,
        validation_engine: IValidationEngine | None = None,
        storypack_builder: IStorypackBuilder | None = None,
        template_engine: ITemplateEngine | None = None,
        output_formatter: IOutputFormatter | None = None,
    ):
        """
        Initialize the orchestrator with dependency injection.

        Args:
            All components can be injected for testing/customization.
            If None, default implementations will be used.
        """
        self.logger = get_logger()

        # Inject dependencies or use defaults
        self._content_parser = content_parser or ContentParser()
        self._metadata_extractor = metadata_extractor or MetadataExtractor()
        self._structure_analyzer = structure_analyzer or StructureAnalyzer()
        self._ai_processor = ai_processor or AIProcessor()
        self._content_classifier = content_classifier or ContentClassifier()
        self._validation_engine = validation_engine or ValidationEngine()
        self._storypack_builder = storypack_builder or StorypackBuilder()
        self._template_engine = template_engine or TemplateEngine()
        self._output_formatter = output_formatter or OutputFormatter()

        # Orchestrator state
        self._ai_initialized = False
        self._templates_loaded = False
        self._available_templates: dict[str, Any] = {}

        log_system_event(
            "storypack_orchestrator",
            "Orchestrator initialized",
            {
                "components_loaded": 9,
                "ai_available": False,  # Will be determined during initialization
                "dependency_injection": True,
            },
        )

    @property
    def output_formatter(self) -> IOutputFormatter:
        """Access to the output formatter component."""
        return self._output_formatter

    async def initialize(self, templates_dir: Path | None = None) -> bool:
        """
        Initialize the orchestrator and all components.

        Args:
            templates_dir: Optional path to templates directory

        Returns:
            True if initialization successful
        """
        log_info("Initializing storypack orchestrator...")

        success = True

        # Initialize AI processor (optional)
        try:
            self._ai_initialized = await self._ai_processor.initialize()
            if self._ai_initialized:
                log_info("✓ AI capabilities initialized")
            else:
                log_warning("⚠ AI capabilities limited or unavailable")
        except Exception as e:
            log_error(f"AI processor initialization failed: {e}")
            self._ai_initialized = False

        # Load templates (optional)
        if templates_dir:
            try:
                self._available_templates = self._template_engine.load_templates(
                    templates_dir
                )
                self._templates_loaded = len(self._available_templates) > 0
                if self._templates_loaded:
                    log_info(f"✓ Loaded {len(self._available_templates)} templates")
                else:
                    log_warning("⚠ No templates found")
            except Exception as e:
                log_error(f"Template loading failed: {e}")
                self._templates_loaded = False

        log_system_event(
            "storypack_orchestrator",
            "Initialization completed",
            {
                "ai_initialized": self._ai_initialized,
                "templates_loaded": self._templates_loaded,
                "template_count": len(self._available_templates),
                "success": success,
            },
        )

        return success

    async def import_storypack(
        self,
        source_path: Path,
        storypack_name: str,
        target_dir: Path,
        import_mode: str = "basic",
    ) -> ImportResult:
        """
        Import a storypack from source directory.

        Args:
            source_path: Source directory containing content
            storypack_name: Name for the new storypack
            target_dir: Target directory for storypack creation
            import_mode: 'basic' or 'ai'

        Returns:
            ImportResult containing operation results
        """
        log_info(f"Starting storypack import: {storypack_name}")

        # Create import context
        context = ImportContext(
            source_path=source_path,
            storypack_name=storypack_name,
            import_mode=import_mode,
            target_path=target_dir / storypack_name,
            templates_available=list(self._available_templates.keys()),
            ai_available=self._ai_initialized and import_mode == "ai",
        )

        # Initialize result
        result = ImportResult(
            success=False,
            storypack_name=storypack_name,
            storypack_path=None,
            files_processed=0,
            generated_files=[],
            processing_time=0.0,
            created_at="",
            errors=[],
            warnings=[],
            metadata={},
        )

        import time
        from datetime import datetime

        start_time = time.time()

        try:
            # Phase 1: Validation
            log_info("Phase 1: Validating import readiness...")
            (
                is_ready,
                validation_issues,
            ) = self._validation_engine.validate_import_readiness(context)

            if not is_ready:
                result.errors.extend(validation_issues)
                log_error(f"Import validation failed: {validation_issues}")
                return result

            if validation_issues:
                result.warnings.extend(validation_issues)

            # Phase 2: Content Discovery
            log_info("Phase 2: Discovering and analyzing content...")
            discovered_files = self._content_parser.discover_files(source_path)

            total_files = sum(len(files) for files in discovered_files.values())
            if total_files == 0:
                result.errors.append("No supported content files found")
                return result

            # Phase 3: Structure Analysis
            log_info("Phase 3: Analyzing directory structure...")
            structure_analysis = self._structure_analyzer.analyze_directory_structure(
                source_path
            )

            # Phase 4: Content Processing
            log_info("Phase 4: Processing content files...")
            processed_content = await self._process_content_files(
                discovered_files, context
            )

            # Phase 5: Storypack Generation
            log_info("Phase 5: Building storypack structure...")
            storypack_path = self._storypack_builder.create_storypack_structure(context)

            # Phase 6: Content Organization
            log_info("Phase 6: Organizing content files...")
            organized_files = self._storypack_builder.organize_content_files(
                discovered_files, storypack_path
            )

            # Phase 7: Metadata Generation
            log_info("Phase 7: Generating storypack metadata...")
            content_summary = self._generate_content_summary(
                processed_content, structure_analysis
            )
            metadata = self._storypack_builder.generate_metadata_file(
                context, content_summary
            )

            # Phase 8: Final Validation
            log_info("Phase 8: Validating generated storypack...")
            (
                is_valid,
                structure_issues,
            ) = self._validation_engine.validate_storypack_structure(storypack_path)

            if structure_issues:
                result.warnings.extend(structure_issues)

            # Set success result
            result.success = is_valid
            result.storypack_path = storypack_path if is_valid else None
            result.files_processed = total_files
            result.processing_time = time.time() - start_time
            result.created_at = datetime.now().isoformat()
            result.generated_files = [storypack_path] if is_valid else []
            result.metadata = {
                "storypack_metadata": metadata,
                "content_summary": content_summary,
                "structure_analysis": structure_analysis,
                "organized_files": {
                    cat: len(files) for cat, files in organized_files.items()
                },
                "import_mode": import_mode,
                "ai_used": context.ai_available,
                "templates_used": self._templates_loaded,
            }

            if result.success:
                log_info(f"✓ Storypack import completed successfully: {storypack_path}")
            else:
                log_error("✗ Storypack import completed with issues")

        except Exception as e:
            log_error(f"Storypack import failed: {e}")
            result.errors.append(f"Import process failed: {e!s}")
            result.success = False
            result.processing_time = time.time() - start_time
            result.created_at = datetime.now().isoformat()

        # Log final result
        log_system_event(
            "storypack_orchestrator",
            "Import completed",
            {
                "success": result.success,
                "storypack_name": storypack_name,
                "files_processed": result.files_processed,
                "errors_count": len(result.errors),
                "warnings_count": len(result.warnings),
                "import_mode": import_mode,
            },
        )

        return result

    async def scan_import_directory(self, import_dir: Path) -> dict[str, Any]:
        """
        Scan import directory for available import candidates.

        Args:
            import_dir: Directory to scan for import candidates

        Returns:
            Dictionary containing scan results
        """
        log_info(f"Scanning import directory: {import_dir}")

        scan_result = {
            "import_directory": str(import_dir),
            "candidates": [],
            "total_candidates": 0,
            "scan_timestamp": datetime.now(UTC).isoformat(),
            "status": "unknown",
        }

        try:
            if not import_dir.exists():
                scan_result["status"] = "directory_not_found"
                scan_result["error"] = f"Import directory does not exist: {import_dir}"
                return scan_result

            candidates = []

            # Scan subdirectories as potential import candidates
            for item in import_dir.iterdir():
                if item.is_dir():
                    candidate_info = await self._analyze_import_candidate(item)
                    if candidate_info["has_content"]:
                        candidates.append(candidate_info)

            scan_result["candidates"] = candidates
            scan_result["total_candidates"] = len(candidates)
            scan_result["status"] = "scan_complete"

            log_info(f"✓ Scan completed: {len(candidates)} candidates found")

        except Exception as e:
            log_error(f"Import directory scan failed: {e}")
            scan_result["status"] = "scan_error"
            scan_result["error"] = str(e)

        return scan_result

    def get_system_status(self) -> dict[str, Any]:
        """Get current system status and capabilities."""
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "ai_available": self._ai_initialized,
            "templates_loaded": self._templates_loaded,
            "template_count": len(self._available_templates),
            "available_templates": list(self._available_templates.keys()),
            "components": {
                "content_parser": True,
                "metadata_extractor": True,
                "structure_analyzer": True,
                "ai_processor": self._ai_initialized,
                "content_classifier": True,
                "validation_engine": True,
                "storypack_builder": True,
                "template_engine": self._templates_loaded,
                "output_formatter": True,
            },
        }

    async def _process_content_files(
        self, discovered_files: dict[str, list[ContentFile]], context: ImportContext
    ) -> dict[str, Any]:
        """Process all discovered content files."""
        processed_content = {
            "files_by_category": {},
            "total_processed": 0,
            "ai_analysis_results": {},
            "classification_results": {},
            "metadata_extractions": {},
        }

        for category, files in discovered_files.items():
            if not files:
                continue

            category_results = []

            for content_file in files:
                try:
                    # Read file content
                    content, encoding = self._content_parser.read_file_content(
                        content_file.path
                    )

                    # Extract metadata
                    metadata = self._metadata_extractor.extract_basic_metadata(
                        content, content_file.path
                    )

                    # Classify content
                    classification = self._content_classifier.classify_by_content(
                        content
                    )

                    file_result = {
                        "file_path": str(content_file.path),
                        "category": category,
                        "classification": classification,
                        "metadata": metadata,
                        "content_length": len(content),
                        "encoding": encoding,
                    }

                    # AI analysis if available
                    if context.ai_available:
                        try:
                            ai_analysis = await self._ai_processor.analyze_content(
                                content, content_file.path, context
                            )
                            file_result["ai_analysis"] = ai_analysis
                        except Exception as e:
                            log_warning(
                                f"AI analysis failed for {content_file.path}: {e}"
                            )
                            file_result["ai_analysis"] = {"error": str(e)}

                    category_results.append(file_result)
                    processed_content["total_processed"] += 1

                except Exception as e:
                    log_error(f"Failed to process file {content_file.path}: {e}")
                    continue

            processed_content["files_by_category"][category] = category_results

        return processed_content

    async def _analyze_import_candidate(self, candidate_path: Path) -> dict[str, Any]:
        """Analyze a potential import candidate directory."""
        candidate_info = {
            "name": candidate_path.name,
            "path": str(candidate_path),
            "has_content": False,
            "file_count": 0,
            "categories": {},
            "estimated_import_time": 0,
            "recommended_mode": "basic",
        }

        try:
            # Discover files
            discovered_files = self._content_parser.discover_files(candidate_path)

            total_files = sum(len(files) for files in discovered_files.values())
            candidate_info["file_count"] = total_files
            candidate_info["has_content"] = total_files > 0

            # Categorize content
            for category, files in discovered_files.items():
                if files:
                    candidate_info["categories"][category] = len(files)

            # Estimate import time (rough heuristic)
            candidate_info["estimated_import_time"] = max(
                30, total_files * 5
            )  # seconds

            # Recommend import mode
            if total_files > 10 and self._ai_initialized:
                candidate_info["recommended_mode"] = "ai"

        except Exception as e:
            log_warning(f"Failed to analyze candidate {candidate_path}: {e}")
            candidate_info["error"] = str(e)

        return candidate_info

    def _generate_content_summary(
        self, processed_content: dict[str, Any], structure_analysis: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate summary of processed content."""
        summary = {
            "total_files": processed_content["total_processed"],
            "files_by_category": {},
            "content_types_detected": set(),
            "ai_analysis_available": bool(processed_content.get("ai_analysis_results")),
            "structure_score": structure_analysis.get("organization_score", 0.0),
            "processing_timestamp": datetime.now(UTC).isoformat(),
        }

        # Summarize by category
        for category, files in processed_content["files_by_category"].items():
            summary["files_by_category"][category] = {
                "count": len(files),
                "total_size": sum(f.get("content_length", 0) for f in files),
                "classifications": [f.get("classification", "unknown") for f in files],
            }

            # Collect unique content types
            for file_info in files:
                summary["content_types_detected"].add(
                    file_info.get("classification", "unknown")
                )

        # Convert set to list for JSON serialization
        summary["content_types_detected"] = list(summary["content_types_detected"])

        return summary
