#!/usr/bin/env python3
"""
OpenChronicle Test Coverage Analysis Tool

Comprehensive analysis to ensure no application capabilities are being skipped in testing.
Analyzes the 54 test files against the 13+ orchestrator system architecture.

This tool maps:
1. Application capabilities (from orchestrators)
2. Test coverage (from test files)
3. Coverage gaps (missing tests)
4. Test completeness assessment

Author: OpenChronicle Development Team
"""

import os
import sys
import json
import ast
import re
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict

# Add utilities path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
from utilities.logging_system import log_system_event, log_info

@dataclass
class TestCoverageResult:
    """Result of test coverage analysis."""
    module_name: str
    total_capabilities: int
    tested_capabilities: int
    coverage_percentage: float
    missing_tests: List[str]
    existing_tests: List[str]
    test_files: List[str]
    

@dataclass
class CapabilityMapping:
    """Mapping of capabilities to tests."""
    orchestrator: str
    capability: str
    method_name: str
    test_exists: bool
    test_files: List[str]


class TestCoverageAnalyzer:
    """Analyze test coverage across OpenChronicle orchestrator systems."""
    
    def __init__(self):
        """Initialize the test coverage analyzer."""
        self.project_root = Path(__file__).parent
        self.tests_dir = self.project_root / "tests"
        self.core_dir = self.project_root / "core"
        
        # Core orchestrator systems to analyze
        self.orchestrator_systems = {
            "database_systems": {
                "orchestrator": "DatabaseOrchestrator",
                "capabilities": [
                    "init_database", "get_connection", "execute_query", "execute_update",
                    "create_tables", "migrate_database", "optimize_database", "backup_database",
                    "fts_search", "create_fts_index", "query_optimization", "health_check",
                    "connection_pooling", "transaction_management"
                ]
            },
            "model_management": {
                "orchestrator": "ModelOrchestrator", 
                "capabilities": [
                    "initialize_adapter", "generate_response", "health_check", "get_status",
                    "list_model_configs", "validate_model_config", "get_fallback_chain",
                    "performance_monitoring", "response_generation", "lifecycle_management",
                    "configuration_management", "dynamic_model_loading", "error_handling",
                    "async_operations", "adapter_management", "registry_management"
                ]
            },
            "character_management": {
                "orchestrator": "CharacterOrchestrator",
                "capabilities": [
                    "load_character", "save_character", "update_character_state", 
                    "validate_character_consistency", "manage_relationships",
                    "character_interactions", "emotional_stability", "trait_management",
                    "character_statistics", "style_adaptation", "behavior_auditing",
                    "multi_character_scenes", "character_tiers", "contradiction_detection"
                ]
            },
            "memory_management": {
                "orchestrator": "MemoryOrchestrator",
                "capabilities": [
                    "get_character_memory", "add_memory_flag", "add_recent_event",
                    "analyze_memory_health", "archive_memory_snapshot", "create_scene_context",
                    "memory_persistence", "consistency_checking", "memory_retrieval",
                    "memory_optimization", "state_restoration", "memory_validation",
                    "character_state_management", "world_state_management"
                ]
            },
            "scene_systems": {
                "orchestrator": "SceneOrchestrator",
                "capabilities": [
                    "save_scene", "load_scene", "list_scenes", "delete_scene",
                    "scene_analysis", "mood_detection", "token_tracking", 
                    "timeline_integration", "scene_validation", "rollback_support",
                    "metadata_management", "scene_tagging", "scene_search"
                ]
            },
            "context_systems": {
                "orchestrator": "ContextOrchestrator", 
                "capabilities": [
                    "build_simple_context", "build_context", "optimize_context",
                    "relevance_scoring", "token_optimization", "context_compression",
                    "context_prioritization", "adaptive_strategies", "context_assembly",
                    "memory_integration", "canon_integration"
                ]
            },
            "narrative_systems": {
                "orchestrator": "NarrativeOrchestrator",
                "capabilities": [
                    "response_intelligence", "narrative_mechanics", "dice_engine",
                    "consistency_validation", "emotional_stability", "quality_assessment",
                    "response_planning", "narrative_branching", "rollback_management",
                    "response_orchestration", "mechanics_orchestration", "state_management"
                ]
            },
            "timeline_systems": {
                "orchestrator": "TimelineOrchestrator",
                "capabilities": [
                    "build_timeline", "list_rollback_points", "create_timeline_entry",
                    "timeline_validation", "event_sequencing", "consistency_checking",
                    "mood_progression", "timeline_optimization", "scene_integration"
                ]
            },
            "content_analysis": {
                "orchestrator": "ContentOrchestrator",
                "capabilities": [
                    "analyze_content", "classify_content", "extract_entities",
                    "sentiment_analysis", "emotion_detection", "nsfw_detection",
                    "risk_assessment", "content_tagging", "relationship_mapping",
                    "transformer_analysis", "traditional_analysis"
                ]
            },
            "image_systems": {
                "orchestrator": "ImageOrchestrator",
                "capabilities": [
                    "generate_image", "process_image", "validate_image_quality",
                    "multi_provider_support", "image_optimization", "batch_processing",
                    "integration_with_narrative", "quality_assessment"
                ]
            },
            "management_systems": {
                "orchestrator": "ManagementOrchestrator",
                "capabilities": [
                    "count_tokens", "estimate_tokens", "select_optimal_model",
                    "create_bookmark", "manage_bookmarks", "token_optimization",
                    "bookmark_organization", "search_functionality", "usage_tracking",
                    "performance_monitoring", "configuration_validation"
                ]
            },
            "security": {
                "orchestrator": "SecurityManager",
                "capabilities": [
                    "validate_user_input", "validate_file_path", "validate_sql_query",
                    "safe_read_file", "safe_write_file", "security_monitoring",
                    "threat_detection", "authentication", "authorization", "rate_limiting",
                    "input_sanitization", "error_handling"
                ]
            },
            "async_operations": {
                "orchestrator": "AsyncOperations",
                "capabilities": [
                    "async_database_operations", "async_memory_operations", 
                    "concurrent_processing", "async_model_calls", "async_scene_generation",
                    "async_context_building", "async_content_analysis", "async_error_handling"
                ]
            }
        }
        
        # Test file categories
        self.test_categories = {
            "unit": [],
            "integration": [],
            "performance": [],
            "mocks": []
        }
        
        # Discovered test methods
        self.test_methods = defaultdict(list)
        self.capability_coverage = {}
        
    def discover_test_files(self) -> Dict[str, List[str]]:
        """Discover all test files in the tests directory."""
        print("🔍 Discovering test files...")
        
        for category in self.test_categories.keys():
            category_dir = self.tests_dir / category
            if category_dir.exists():
                for test_file in category_dir.glob("test_*.py"):
                    self.test_categories[category].append(str(test_file.relative_to(self.tests_dir)))
        
        # Also check root tests directory
        for test_file in self.tests_dir.glob("test_*.py"):
            self.test_categories["unit"].append(str(test_file.relative_to(self.tests_dir)))
        
        total_files = sum(len(files) for files in self.test_categories.values())
        print(f"   Found {total_files} test files across categories")
        
        for category, files in self.test_categories.items():
            if files:
                print(f"   • {category}: {len(files)} files")
        
        return self.test_categories
    
    def analyze_test_file(self, test_file_path: Path) -> List[str]:
        """Analyze a test file to extract test methods."""
        try:
            with open(test_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse the AST to find test methods
            tree = ast.parse(content)
            test_methods = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                    test_methods.append(node.name)
                elif isinstance(node, ast.AsyncFunctionDef) and node.name.startswith('test_'):
                    test_methods.append(node.name)
            
            return test_methods
        except Exception as e:
            print(f"   ⚠️  Error analyzing {test_file_path}: {e}")
            return []
    
    def map_tests_to_capabilities(self) -> Dict[str, CapabilityMapping]:
        """Map test methods to orchestrator capabilities."""
        print("\n🔗 Mapping tests to capabilities...")
        
        capability_mappings = {}
        
        for system_name, system_info in self.orchestrator_systems.items():
            orchestrator = system_info["orchestrator"]
            capabilities = system_info["capabilities"]
            
            for capability in capabilities:
                mapping = CapabilityMapping(
                    orchestrator=orchestrator,
                    capability=capability,
                    method_name=capability,
                    test_exists=False,
                    test_files=[]
                )
                
                # Look for tests that might cover this capability
                for category, files in self.test_categories.items():
                    for file_path in files:
                        full_path = self.tests_dir / file_path
                        if not full_path.exists():
                            continue
                            
                        test_methods = self.analyze_test_file(full_path)
                        
                        # Check if any test method relates to this capability
                        for test_method in test_methods:
                            if self._is_capability_tested(capability, test_method, file_path):
                                mapping.test_exists = True
                                mapping.test_files.append(file_path)
                
                capability_mappings[f"{system_name}.{capability}"] = mapping
        
        return capability_mappings
    
    def _is_capability_tested(self, capability: str, test_method: str, file_path: str) -> bool:
        """Determine if a test method covers a specific capability."""
        # Convert capability to test-friendly format
        capability_words = re.findall(r'[A-Za-z]+', capability.lower())
        test_words = re.findall(r'[A-Za-z]+', test_method.lower())
        file_words = re.findall(r'[A-Za-z]+', file_path.lower())
        
        # Check for direct matches
        for cap_word in capability_words:
            if cap_word in test_words or cap_word in file_words:
                return True
        
        # Check for semantic matches
        semantic_matches = {
            'generate_response': ['generate', 'response', 'model', 'adapter'],
            'health_check': ['health', 'status', 'monitor'],
            'save_scene': ['save', 'scene', 'create'],
            'load_scene': ['load', 'scene', 'retrieve'],
            'memory': ['memory', 'character', 'state'],
            'database': ['database', 'db', 'connection', 'query'],
            'async': ['async', 'concurrent', 'background'],
            'orchestrator': ['orchestrator', 'init', 'initialization'],
            'performance': ['performance', 'optimization', 'monitoring'],
            'error': ['error', 'exception', 'handling', 'failure'],
            'config': ['config', 'configuration', 'settings'],
            'integration': ['integration', 'workflow', 'complete'],
            'validation': ['validation', 'validate', 'check']
        }
        
        for key, keywords in semantic_matches.items():
            if key in capability.lower():
                for keyword in keywords:
                    if keyword in test_words or keyword in file_words:
                        return True
        
        return False
    
    def generate_coverage_report(self, capability_mappings: Dict[str, CapabilityMapping]) -> List[TestCoverageResult]:
        """Generate comprehensive coverage report."""
        print("\n📊 Generating coverage report...")
        
        coverage_results = []
        
        for system_name, system_info in self.orchestrator_systems.items():
            orchestrator = system_info["orchestrator"]
            capabilities = system_info["capabilities"]
            
            tested_capabilities = []
            missing_capabilities = []
            test_files = set()
            
            for capability in capabilities:
                mapping_key = f"{system_name}.{capability}"
                mapping = capability_mappings.get(mapping_key)
                
                if mapping and mapping.test_exists:
                    tested_capabilities.append(capability)
                    test_files.update(mapping.test_files)
                else:
                    missing_capabilities.append(capability)
            
            coverage_percentage = (len(tested_capabilities) / len(capabilities)) * 100 if capabilities else 0
            
            result = TestCoverageResult(
                module_name=system_name,
                total_capabilities=len(capabilities),
                tested_capabilities=len(tested_capabilities),
                coverage_percentage=coverage_percentage,
                missing_tests=missing_capabilities,
                existing_tests=tested_capabilities,
                test_files=list(test_files)
            )
            
            coverage_results.append(result)
        
        return coverage_results
    
    def identify_critical_gaps(self, coverage_results: List[TestCoverageResult]) -> Dict[str, List[str]]:
        """Identify critical testing gaps that need immediate attention."""
        print("\n🎯 Identifying critical testing gaps...")
        
        critical_gaps = {
            "high_priority": [],
            "medium_priority": [],
            "low_priority": []
        }
        
        # Critical capabilities that must be tested
        critical_capabilities = {
            "generate_response", "save_scene", "load_scene", "get_character_memory",
            "init_database", "execute_query", "health_check", "error_handling",
            "async_operations", "orchestrator_initialization"
        }
        
        for result in coverage_results:
            if result.coverage_percentage < 50:
                critical_gaps["high_priority"].append(
                    f"{result.module_name}: {result.coverage_percentage:.1f}% coverage"
                )
            elif result.coverage_percentage < 75:
                critical_gaps["medium_priority"].append(
                    f"{result.module_name}: {result.coverage_percentage:.1f}% coverage"
                )
            else:
                critical_gaps["low_priority"].append(
                    f"{result.module_name}: {result.coverage_percentage:.1f}% coverage"
                )
            
            # Check for missing critical capabilities
            for missing in result.missing_tests:
                for critical in critical_capabilities:
                    if critical.lower() in missing.lower():
                        critical_gaps["high_priority"].append(
                            f"CRITICAL: {result.module_name}.{missing} not tested"
                        )
        
        return critical_gaps
    
    def generate_test_recommendations(self, coverage_results: List[TestCoverageResult], 
                                    critical_gaps: Dict[str, List[str]]) -> List[str]:
        """Generate specific test creation recommendations."""
        print("\n💡 Generating test recommendations...")
        
        recommendations = []
        
        # Overall recommendations
        total_capabilities = sum(r.total_capabilities for r in coverage_results)
        total_tested = sum(r.tested_capabilities for r in coverage_results)
        overall_coverage = (total_tested / total_capabilities) * 100 if total_capabilities else 0
        
        recommendations.append(f"📊 OVERALL COVERAGE: {overall_coverage:.1f}% ({total_tested}/{total_capabilities})")
        recommendations.append("")
        
        # Priority recommendations
        if critical_gaps["high_priority"]:
            recommendations.append("🚨 HIGH PRIORITY - Address immediately:")
            for gap in critical_gaps["high_priority"][:5]:  # Top 5 critical gaps
                recommendations.append(f"   • {gap}")
            recommendations.append("")
        
        # System-specific recommendations
        for result in sorted(coverage_results, key=lambda x: x.coverage_percentage):
            if result.coverage_percentage < 80:
                recommendations.append(f"📝 {result.module_name.upper()} ({result.coverage_percentage:.1f}% coverage):")
                
                if result.missing_tests:
                    recommendations.append("   Missing tests for:")
                    for missing in result.missing_tests[:3]:  # Top 3 missing
                        recommendations.append(f"      - {missing}")
                
                if result.test_files:
                    recommendations.append(f"   Existing test files: {len(result.test_files)}")
                else:
                    recommendations.append("   ⚠️  NO TEST FILES FOUND")
                
                recommendations.append("")
        
        # Test file creation recommendations
        systems_without_tests = [r for r in coverage_results if not r.test_files]
        if systems_without_tests:
            recommendations.append("📁 CREATE THESE TEST FILES:")
            for result in systems_without_tests:
                test_file = f"test_{result.module_name.replace('_', '_')}_orchestrator.py"
                recommendations.append(f"   • tests/unit/{test_file}")
            recommendations.append("")
        
        # Integration test recommendations
        recommendations.append("🔗 INTEGRATION TEST PRIORITIES:")
        recommendations.append("   • Complete workflow testing (scene generation to memory storage)")
        recommendations.append("   • Cross-orchestrator communication testing")
        recommendations.append("   • Error propagation and recovery testing")
        recommendations.append("   • Performance under load testing")
        recommendations.append("")
        
        return recommendations
    
    def save_analysis_report(self, coverage_results: List[TestCoverageResult], 
                           critical_gaps: Dict[str, List[str]], 
                           recommendations: List[str]) -> str:
        """Save the complete analysis report to file."""
        report_file = self.project_root / "test_coverage_analysis_report.md"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# OpenChronicle Test Coverage Analysis Report\n\n")
            f.write("**Generated**: OpenChronicle Quality Consolidation Phase\n")
            f.write("**Purpose**: Ensure no application capabilities are being skipped in testing\n\n")
            
            # Executive Summary
            f.write("## 📊 Executive Summary\n\n")
            total_capabilities = sum(r.total_capabilities for r in coverage_results)
            total_tested = sum(r.tested_capabilities for r in coverage_results)
            overall_coverage = (total_tested / total_capabilities) * 100 if total_capabilities else 0
            
            f.write(f"- **Total Application Capabilities**: {total_capabilities}\n")
            f.write(f"- **Tested Capabilities**: {total_tested}\n")
            f.write(f"- **Overall Coverage**: {overall_coverage:.1f}%\n")
            f.write(f"- **Test Files Analyzed**: {sum(len(files) for files in self.test_categories.values())}\n\n")
            
            # Coverage by System
            f.write("## 🎯 Coverage by Orchestrator System\n\n")
            f.write("| System | Capabilities | Tested | Coverage | Status |\n")
            f.write("|--------|-------------|--------|----------|--------|\n")
            
            for result in sorted(coverage_results, key=lambda x: -x.coverage_percentage):
                status = "🟢" if result.coverage_percentage >= 80 else "🟡" if result.coverage_percentage >= 50 else "🔴"
                f.write(f"| {result.module_name} | {result.total_capabilities} | {result.tested_capabilities} | {result.coverage_percentage:.1f}% | {status} |\n")
            
            f.write("\n")
            
            # Critical Gaps
            f.write("## 🚨 Critical Testing Gaps\n\n")
            for priority, gaps in critical_gaps.items():
                if gaps:
                    f.write(f"### {priority.replace('_', ' ').title()}\n\n")
                    for gap in gaps:
                        f.write(f"- {gap}\n")
                    f.write("\n")
            
            # Detailed System Analysis
            f.write("## 📋 Detailed System Analysis\n\n")
            for result in coverage_results:
                f.write(f"### {result.module_name.replace('_', ' ').title()}\n\n")
                f.write(f"**Coverage**: {result.coverage_percentage:.1f}% ({result.tested_capabilities}/{result.total_capabilities})\n\n")
                
                if result.test_files:
                    f.write("**Test Files**:\n")
                    for test_file in result.test_files:
                        f.write(f"- {test_file}\n")
                    f.write("\n")
                else:
                    f.write("**⚠️ No test files found**\n\n")
                
                if result.existing_tests:
                    f.write("**Tested Capabilities**:\n")
                    for capability in result.existing_tests:
                        f.write(f"- ✅ {capability}\n")
                    f.write("\n")
                
                if result.missing_tests:
                    f.write("**Missing Tests**:\n")
                    for capability in result.missing_tests:
                        f.write(f"- ❌ {capability}\n")
                    f.write("\n")
            
            # Recommendations
            f.write("## 💡 Recommendations\n\n")
            for recommendation in recommendations:
                f.write(f"{recommendation}\n")
            
            # Test File Structure
            f.write("## 📁 Current Test File Structure\n\n")
            for category, files in self.test_categories.items():
                if files:
                    f.write(f"### {category.title()}\n\n")
                    for file_path in sorted(files):
                        f.write(f"- {file_path}\n")
                    f.write("\n")
        
        return str(report_file)
    
    def run_complete_analysis(self) -> Dict[str, Any]:
        """Run the complete test coverage analysis."""
        print("🔍 OpenChronicle Test Coverage Analysis")
        print("========================================")
        print("Following user directive: 'review all tests and ensure that we are fully testing our applications capabilities and not skipping tests'")
        print()
        
        # Step 1: Discover test files
        test_files = self.discover_test_files()
        
        # Step 2: Map tests to capabilities
        capability_mappings = self.map_tests_to_capabilities()
        
        # Step 3: Generate coverage report
        coverage_results = self.generate_coverage_report(capability_mappings)
        
        # Step 4: Identify critical gaps
        critical_gaps = self.identify_critical_gaps(coverage_results)
        
        # Step 5: Generate recommendations
        recommendations = self.generate_test_recommendations(coverage_results, critical_gaps)
        
        # Step 6: Save complete report
        report_file = self.save_analysis_report(coverage_results, critical_gaps, recommendations)
        
        # Step 7: Display summary
        self.display_analysis_summary(coverage_results, critical_gaps, recommendations, report_file)
        
        return {
            "test_files": test_files,
            "coverage_results": [asdict(r) for r in coverage_results],
            "critical_gaps": critical_gaps,
            "recommendations": recommendations,
            "report_file": report_file
        }
    
    def display_analysis_summary(self, coverage_results: List[TestCoverageResult],
                                critical_gaps: Dict[str, List[str]], 
                                recommendations: List[str],
                                report_file: str):
        """Display the analysis summary."""
        print("\n" + "="*60)
        print("🎯 TEST COVERAGE ANALYSIS SUMMARY")
        print("="*60)
        
        # Overall statistics
        total_capabilities = sum(r.total_capabilities for r in coverage_results)
        total_tested = sum(r.tested_capabilities for r in coverage_results)
        overall_coverage = (total_tested / total_capabilities) * 100 if total_capabilities else 0
        
        print(f"📊 OVERALL COVERAGE:")
        print(f"   • Total capabilities: {total_capabilities}")
        print(f"   • Tested capabilities: {total_tested}")
        print(f"   • Coverage percentage: {overall_coverage:.1f}%")
        
        # System summary
        print("\n🎯 SYSTEM COVERAGE SUMMARY:")
        for result in sorted(coverage_results, key=lambda x: -x.coverage_percentage):
            status = "🟢" if result.coverage_percentage >= 80 else "🟡" if result.coverage_percentage >= 50 else "🔴"
            print(f"   {status} {result.module_name}: {result.coverage_percentage:.1f}% ({result.tested_capabilities}/{result.total_capabilities})")
        
        # Critical gaps summary
        if critical_gaps["high_priority"]:
            print(f"\n🚨 CRITICAL GAPS ({len(critical_gaps['high_priority'])}):")
            for gap in critical_gaps["high_priority"][:3]:
                print(f"   • {gap}")
            if len(critical_gaps["high_priority"]) > 3:
                print(f"   • ... and {len(critical_gaps['high_priority']) - 3} more")
        
        # Top recommendations
        print("\n💡 TOP RECOMMENDATIONS:")
        for rec in recommendations[:5]:
            if rec.strip():
                print(f"   • {rec.strip()}")
        
        print(f"\n📄 Complete report saved: {report_file}")
        print("="*60)
        print("🎉 TEST COVERAGE ANALYSIS COMPLETE")
        print("="*60)


def main():
    """Main entry point for test coverage analysis."""
    analyzer = TestCoverageAnalyzer()
    
    try:
        # Log the analysis start
        log_system_event("test_coverage_analysis_start", "Comprehensive test coverage analysis initiated")
        
        # Run the complete analysis
        results = analyzer.run_complete_analysis()
        
        # Log completion
        log_system_event("test_coverage_analysis_complete", 
                        f"Analysis complete - {results['coverage_results']}")
        
        return results
        
    except Exception as e:
        print(f"\n❌ Error during test coverage analysis: {e}")
        log_system_event("test_coverage_analysis_error", f"Analysis failed: {e}")
        raise


if __name__ == "__main__":
    main()
