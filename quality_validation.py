#!/usr/bin/env python3
"""
OpenChronicle Quality Validation System
=====================================

Comprehensive validation of all existing systems before new development.
Follows user directive: "make everything work REALLY WELL first"
"""

import sys
import os
import importlib
import asyncio
from pathlib import Path

# Fix Python path for imports
sys.path.insert(0, '.')

class QualityValidator:
    """Validates OpenChronicle system health and quality"""
    
    def __init__(self):
        self.issues = []
        self.passed = []
        self.modules_tested = 0
        
    def log_issue(self, module, issue):
        self.issues.append(f"❌ {module}: {issue}")
        
    def log_pass(self, module, check):
        self.passed.append(f"✅ {module}: {check}")
        
    def validate_core_structure(self):
        """Validate core module structure and imports"""
        print("\n🔍 VALIDATING CORE SYSTEM STRUCTURE")
        print("=" * 50)
        
        core_modules = [
            'core.model_management',
            'core.memory_management', 
            'core.character_management',
            'core.narrative_systems',
            'core.scene_systems',
            'core.timeline_systems'
        ]
        
        for module_name in core_modules:
            try:
                module = importlib.import_module(module_name)
                self.log_pass(module_name, "Import successful")
                self.modules_tested += 1
                
                # Check for key classes/functions
                if hasattr(module, '__all__'):
                    exports = len(module.__all__)
                    self.log_pass(module_name, f"{exports} public exports defined")
                    
            except ImportError as e:
                self.log_issue(module_name, f"Import failed: {e}")
            except Exception as e:
                self.log_issue(module_name, f"Unexpected error: {e}")
                
    def validate_configuration(self):
        """Validate configuration files and registry"""
        print("\n🔍 VALIDATING CONFIGURATION SYSTEM")
        print("=" * 50)
        
        config_files = [
            'config/system_config.json',
            'config/registry_settings.json'
        ]
        
        for config_file in config_files:
            if os.path.exists(config_file):
                try:
                    import json
                    with open(config_file, 'r') as f:
                        data = json.load(f)
                    self.log_pass(config_file, f"Valid JSON with {len(data)} keys")
                except json.JSONDecodeError as e:
                    self.log_issue(config_file, f"Invalid JSON: {e}")
            else:
                self.log_issue(config_file, "File missing")
                
    def validate_test_infrastructure(self):
        """Check test coverage and quality"""
        print("\n🔍 VALIDATING TEST INFRASTRUCTURE")
        print("=" * 50)
        
        test_files = list(Path('tests').glob('test_*.py'))
        self.log_pass('test_infrastructure', f"{len(test_files)} test files found")
        
        # Check if tests can be imported
        test_imports = 0
        for test_file in test_files[:5]:  # Sample first 5
            module_name = f"tests.{test_file.stem}"
            try:
                importlib.import_module(module_name)
                test_imports += 1
            except Exception as e:
                self.log_issue(module_name, f"Import failed: {e}")
                
        if test_imports > 0:
            self.log_pass('test_infrastructure', f"{test_imports} test modules importable")
            
    def validate_storage_systems(self):
        """Validate storage and data systems"""
        print("\n🔍 VALIDATING STORAGE SYSTEMS")
        print("=" * 50)
        
        storage_dirs = ['storage', 'logs', 'templates']
        for storage_dir in storage_dirs:
            if os.path.exists(storage_dir):
                files = len(os.listdir(storage_dir))
                self.log_pass(storage_dir, f"Directory exists with {files} items")
            else:
                self.log_issue(storage_dir, "Directory missing")
                
    async def validate_async_systems(self):
        """Test async system components"""
        print("\n🔍 VALIDATING ASYNC SYSTEMS")
        print("=" * 50)
        
        try:
            # Basic async functionality test
            await asyncio.sleep(0.1)
            self.log_pass('async_runtime', "Async execution working")
            
            # Test if model management supports async
            from core.model_management import ModelOrchestrator
            orchestrator = ModelOrchestrator()
            self.log_pass('model_orchestrator', "Can instantiate ModelOrchestrator")
            
        except Exception as e:
            self.log_issue('async_systems', f"Async validation failed: {e}")
            
    def generate_report(self):
        """Generate comprehensive quality report"""
        print("\n" + "=" * 60)
        print("🎯 OPENCHRONICLE QUALITY VALIDATION REPORT")
        print("=" * 60)
        
        print(f"\n📊 SUMMARY:")
        print(f"   • Modules tested: {self.modules_tested}")
        print(f"   • Checks passed: {len(self.passed)}")
        print(f"   • Issues found: {len(self.issues)}")
        
        if self.passed:
            print(f"\n✅ PASSING SYSTEMS ({len(self.passed)}):")
            for check in self.passed:
                print(f"   {check}")
                
        if self.issues:
            print(f"\n❌ ISSUES TO RESOLVE ({len(self.issues)}):")
            for issue in self.issues:
                print(f"   {issue}")
            print(f"\n🔧 RECOMMENDATION:")
            print(f"   Resolve these {len(self.issues)} issues before proceeding")
        else:
            print(f"\n🎉 EXCELLENT! No critical issues found.")
            print(f"   System ready for quality consolidation phase.")
            
        # Quality score
        total_checks = len(self.passed) + len(self.issues)
        if total_checks > 0:
            quality_score = (len(self.passed) / total_checks) * 100
            print(f"\n📈 QUALITY SCORE: {quality_score:.1f}%")
            
            if quality_score >= 90:
                print("   🌟 EXCELLENT - Ready for advanced features")
            elif quality_score >= 75:
                print("   ✅ GOOD - Minor fixes needed")
            elif quality_score >= 50:
                print("   ⚠️  NEEDS WORK - Address major issues")
            else:
                print("   🚨 CRITICAL - Requires significant fixes")

async def main():
    """Run comprehensive quality validation"""
    print("🚀 OpenChronicle Quality Validation Starting...")
    print("   Following user directive: 'make everything work REALLY WELL'")
    
    validator = QualityValidator()
    
    # Run all validation checks
    validator.validate_core_structure()
    validator.validate_configuration()
    validator.validate_test_infrastructure()
    validator.validate_storage_systems()
    await validator.validate_async_systems()
    
    # Generate final report
    validator.generate_report()
    
    return len(validator.issues) == 0

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
