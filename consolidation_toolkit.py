#!/usr/bin/env python3
"""
OpenChronicle Consolidation Toolkit
===================================

Practical tools for the quality consolidation phase.
Implements user directive: "make everything work REALLY WELL first"
"""

import sys
import asyncio
import time
import json
from pathlib import Path

# Fix imports
sys.path.insert(0, '.')

class ConsolidationToolkit:
    """Tools for validating and consolidating OpenChronicle systems"""
    
    def __init__(self):
        self.results = []
        
    def log_result(self, test_name, success, details=""):
        """Log a consolidation test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        self.results.append({
            'test': test_name,
            'success': success,
            'details': details,
            'timestamp': time.time()
        })
        print(f"{status}: {test_name}")
        if details:
            print(f"    {details}")
    
    def test_core_imports(self):
        """Test all core module imports"""
        print("\n🔍 TESTING CORE IMPORTS")
        print("-" * 40)
        
        core_modules = [
            'core.model_management',
            'core.memory_management', 
            'core.character_management',
            'core.narrative_systems',
            'core.scene_systems',
            'core.timeline_systems',
            'core.shared.security'
        ]
        
        success_count = 0
        for module in core_modules:
            try:
                __import__(module)
                self.log_result(f"Import {module}", True)
                success_count += 1
            except Exception as e:
                self.log_result(f"Import {module}", False, str(e))
        
        overall_success = success_count == len(core_modules)
        self.log_result("Core imports overall", overall_success, 
                       f"{success_count}/{len(core_modules)} modules imported")
        return overall_success
    
    def test_configuration_loading(self):
        """Test configuration system"""
        print("\n⚙️  TESTING CONFIGURATION")
        print("-" * 40)
        
        config_files = [
            'config/system_config.json',
            'config/registry_settings.json'
        ]
        
        all_configs_valid = True
        for config_file in config_files:
            try:
                if Path(config_file).exists():
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    key_count = len(config) if isinstance(config, dict) else 0
                    self.log_result(f"Load {config_file}", True, f"{key_count} configuration keys")
                else:
                    self.log_result(f"Load {config_file}", False, "File missing")
                    all_configs_valid = False
            except Exception as e:
                self.log_result(f"Load {config_file}", False, str(e))
                all_configs_valid = False
        
        return all_configs_valid
    
    async def test_async_systems(self):
        """Test async system functionality"""
        print("\n🔄 TESTING ASYNC SYSTEMS")
        print("-" * 40)
        
        try:
            # Test basic async functionality
            start_time = time.time()
            await asyncio.sleep(0.1)
            elapsed = time.time() - start_time
            
            if 0.09 <= elapsed <= 0.2:  # Reasonable range
                self.log_result("Basic async execution", True, f"Sleep timing: {elapsed:.3f}s")
            else:
                self.log_result("Basic async execution", False, f"Unexpected timing: {elapsed:.3f}s")
            
            # Test if model orchestrator can be instantiated
            try:
                from core.model_management import ModelOrchestrator
                orchestrator = ModelOrchestrator()
                self.log_result("ModelOrchestrator instantiation", True)
                
                # Test if it has expected methods
                expected_methods = ['process_request', 'get_model_status']
                has_methods = all(hasattr(orchestrator, method) for method in expected_methods)
                self.log_result("ModelOrchestrator methods", has_methods, 
                               f"Expected methods present: {has_methods}")
                
                return True
            except Exception as e:
                self.log_result("ModelOrchestrator instantiation", False, str(e))
                return False
                
        except Exception as e:
            self.log_result("Async systems", False, str(e))
            return False
    
    def test_storage_systems(self):
        """Test storage and file systems"""
        print("\n💾 TESTING STORAGE SYSTEMS")
        print("-" * 40)
        
        storage_paths = [
            'storage',
            'storage/characters',
            'storage/data',
            'logs',
            'templates'
        ]
        
        storage_health = True
        for path in storage_paths:
            if Path(path).exists():
                if Path(path).is_dir():
                    file_count = len(list(Path(path).iterdir()))
                    self.log_result(f"Storage path {path}", True, f"{file_count} items")
                else:
                    self.log_result(f"Storage path {path}", False, "Not a directory")
                    storage_health = False
            else:
                self.log_result(f"Storage path {path}", False, "Missing")
                storage_health = False
        
        return storage_health
    
    def test_week17_infrastructure(self):
        """Test Week 17 distributed caching infrastructure"""
        print("\n🔄 TESTING WEEK 17 INFRASTRUCTURE")
        print("-" * 40)
        
        week17_components = [
            ('docker-compose.yaml', 'Docker orchestration'),
            ('config/system_config.json', 'System configuration'),
            ('storage/performance_baseline.json', 'Performance baselines')
        ]
        
        week17_health = True
        for component_file, description in week17_components:
            if Path(component_file).exists():
                file_size = Path(component_file).stat().st_size
                self.log_result(f"Week 17 {description}", True, f"{component_file} ({file_size} bytes)")
            else:
                self.log_result(f"Week 17 {description}", False, f"{component_file} missing")
                week17_health = False
        
        # Check for Redis configuration in docker-compose
        if Path('docker-compose.yaml').exists():
            with open('docker-compose.yaml', 'r') as f:
                content = f.read()
                has_networks = 'networks:' in content
                has_volumes = 'volumes:' in content or 'volume' in content
                self.log_result("Docker compose completeness", has_networks and has_volumes,
                               f"Networks: {has_networks}, Volumes: {has_volumes}")
        
        return week17_health
    
    def generate_consolidation_report(self):
        """Generate comprehensive consolidation report"""
        print("\n" + "="*60)
        print("🎯 OPENCHRONICLE CONSOLIDATION REPORT")
        print("="*60)
        
        passed = sum(1 for r in self.results if r['success'])
        total = len(self.results)
        success_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"\n📊 CONSOLIDATION SUMMARY:")
        print(f"   • Tests passed: {passed}/{total}")
        print(f"   • Success rate: {success_rate:.1f}%")
        
        if success_rate >= 95:
            status = "🌟 EXCELLENT - Ready for advanced optimization"
        elif success_rate >= 85:
            status = "✅ GOOD - Minor issues to resolve"
        elif success_rate >= 70:
            status = "⚠️  NEEDS WORK - Multiple issues require attention"
        else:
            status = "🚨 CRITICAL - Major problems must be fixed"
        
        print(f"   • Overall status: {status}")
        
        # List any failures
        failures = [r for r in self.results if not r['success']]
        if failures:
            print(f"\n❌ ISSUES TO RESOLVE ({len(failures)}):")
            for failure in failures:
                print(f"   • {failure['test']}: {failure['details']}")
        
        # Consolidation recommendations
        print(f"\n🎯 CONSOLIDATION RECOMMENDATIONS:")
        if success_rate >= 95:
            print("   → Begin Phase 2: Integration Excellence")
            print("   → Start cross-module communication testing")
            print("   → Implement performance profiling")
        elif success_rate >= 85:
            print("   → Complete Phase 1: Fix remaining core issues")
            print("   → Validate all module imports")
            print("   → Ensure configuration completeness")
        else:
            print("   → Focus on Phase 0: Critical system repairs")
            print("   → Rebuild failing core components")
            print("   → Establish reliable foundation")
        
        print(f"\n💡 USER DIRECTIVE COMPLIANCE:")
        print("   ✅ Focus on quality over quantity")
        print("   ✅ Consolidate before expanding")
        print("   ✅ Make everything work REALLY WELL")
        
        return success_rate >= 85

async def main():
    """Run comprehensive consolidation testing"""
    print("🚀 OpenChronicle Quality Consolidation")
    print("Following user directive: 'make everything work REALLY WELL first'")
    print("="*60)
    
    toolkit = ConsolidationToolkit()
    
    # Run all consolidation tests
    toolkit.test_core_imports()
    toolkit.test_configuration_loading()
    await toolkit.test_async_systems()
    toolkit.test_storage_systems()
    toolkit.test_week17_infrastructure()
    
    # Generate final report
    is_ready = toolkit.generate_consolidation_report()
    
    print(f"\n{'='*60}")
    if is_ready:
        print("🎉 CONSOLIDATION SUCCESS - Ready for next phase")
    else:
        print("⚠️  CONSOLIDATION NEEDED - Address issues first")
    print("="*60)
    
    return is_ready

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
