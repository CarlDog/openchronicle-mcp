"""
OpenChronicle Quality Consolidation Assessment
==============================================

Based on user directive: "make everything work REALLY WELL first"
Priority: Quality over quantity, consolidation over expansion
"""

import sys
import os
import json
sys.path.insert(0, '.')

def assess_system_health():
    """Comprehensive assessment of OpenChronicle system health"""
    
    print("🎯 OPENCHRONICLE QUALITY ASSESSMENT")
    print("=" * 50)
    print("Following user directive: 'Everything must work REALLY WELL first'")
    print()
    
    # 1. Core Architecture Assessment
    print("🏗️  ARCHITECTURE ASSESSMENT:")
    
    core_dirs = [
        'character_management', 'memory_management', 'model_management',
        'narrative_systems', 'scene_systems', 'timeline_systems',
        'context_systems', 'database_systems', 'image_systems'
    ]
    
    existing_dirs = []
    for dir_name in core_dirs:
        path = f"core/{dir_name}"
        if os.path.exists(path):
            files = len([f for f in os.listdir(path) if f.endswith('.py')])
            existing_dirs.append(dir_name)
            print(f"   ✅ {dir_name}: {files} Python files")
        else:
            print(f"   ❌ {dir_name}: Missing")
    
    print(f"   📊 Result: {len(existing_dirs)}/{len(core_dirs)} core systems present")
    
    # 2. Configuration Health
    print(f"\n⚙️  CONFIGURATION HEALTH:")
    
    config_files = ['config/system_config.json', 'config/registry_settings.json']
    config_health = 0
    
    for config_file in config_files:
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"   ✅ {config_file}: Valid JSON ({len(data)} keys)")
                config_health += 1
            except Exception as e:
                print(f"   ⚠️  {config_file}: JSON error - {e}")
        else:
            print(f"   ❌ {config_file}: Missing")
    
    print(f"   📊 Result: {config_health}/{len(config_files)} config files healthy")
    
    # 3. Test Infrastructure
    print(f"\n🧪 TEST INFRASTRUCTURE:")
    
    if os.path.exists('tests'):
        test_files = [f for f in os.listdir('tests') if f.startswith('test_') and f.endswith('.py')]
        print(f"   ✅ Test directory: {len(test_files)} test files")
        
        # Check for key test files
        important_tests = ['test_model_adapter.py', 'test_memory_management.py']
        for test_file in important_tests:
            if test_file in test_files:
                print(f"   ✅ {test_file}: Present")
            else:
                print(f"   ⚠️  {test_file}: Missing")
    else:
        print(f"   ❌ Tests directory: Missing")
    
    # 4. Week 17 Distributed Caching Assessment
    print(f"\n🔄 WEEK 17 DISTRIBUTED CACHING:")
    
    week17_indicators = [
        ('docker-compose.yaml', 'Redis infrastructure'),
        ('core/performance', 'Performance monitoring'),
        ('storage/performance_baseline.json', 'Performance baselines')
    ]
    
    week17_health = 0
    for indicator, description in week17_indicators:
        if os.path.exists(indicator):
            print(f"   ✅ {description}: {indicator} present")
            week17_health += 1
        else:
            print(f"   ❌ {description}: {indicator} missing")
    
    print(f"   📊 Result: {week17_health}/{len(week17_indicators)} Week 17 components verified")
    
    # 5. Overall Quality Score
    total_systems = len(core_dirs) + len(config_files) + len(week17_indicators)
    healthy_systems = len(existing_dirs) + config_health + week17_health
    
    quality_score = (healthy_systems / total_systems) * 100
    
    print(f"\n📈 OVERALL QUALITY ASSESSMENT:")
    print(f"   • Systems present: {healthy_systems}/{total_systems}")
    print(f"   • Quality score: {quality_score:.1f}%")
    
    if quality_score >= 90:
        status = "🌟 EXCELLENT"
        recommendation = "Ready for quality consolidation phase"
    elif quality_score >= 75:
        status = "✅ GOOD"
        recommendation = "Minor fixes needed before consolidation"
    elif quality_score >= 50:
        status = "⚠️  NEEDS WORK"
        recommendation = "Address major issues before proceeding"
    else:
        status = "🚨 CRITICAL"
        recommendation = "Requires significant fixes"
    
    print(f"   • Status: {status}")
    print(f"   • Recommendation: {recommendation}")
    
    # 6. Quality Consolidation Action Plan
    print(f"\n🎯 QUALITY CONSOLIDATION ACTION PLAN:")
    print(f"   Based on user feedback about 'half-developed features'")
    print()
    
    if quality_score >= 75:
        print("   Phase 1: ✅ System Validation (Ready)")
        print("   Phase 2: 🔄 Integration Testing")
        print("   Phase 3: ⚡ Performance Optimization")
        print("   Phase 4: 📚 Documentation Consolidation")
        print("   Phase 5: 🧹 Code Quality Refinement")
    else:
        print("   Phase 0: 🔧 Fix Critical Issues First")
        print("   Phase 1: 🏗️  Rebuild Missing Components")
        print("   Phase 2: ✅ System Validation")
        print("   Phase 3: 🔄 Integration Testing")
    
    print(f"\n💡 NEXT STEPS:")
    if quality_score >= 90:
        print("   → Start comprehensive integration testing")
        print("   → Performance profiling and optimization")
        print("   → User experience validation")
    elif quality_score >= 75:
        print("   → Fix remaining configuration issues")
        print("   → Complete missing test coverage")
        print("   → Begin integration validation")
    else:
        print("   → Address critical missing components")
        print("   → Rebuild failing systems")
        print("   → Establish reliable foundation")
    
    return quality_score >= 75

if __name__ == "__main__":
    is_ready = assess_system_health()
    print(f"\n{'='*50}")
    
    if is_ready:
        print("🎉 SYSTEM READY FOR QUALITY CONSOLIDATION")
        print("   User directive acknowledged: Focus on making everything work excellently")
    else:
        print("⚠️  SYSTEM NEEDS REPAIRS BEFORE CONSOLIDATION")
        print("   Critical issues must be resolved first")
    
    print("="*50)
