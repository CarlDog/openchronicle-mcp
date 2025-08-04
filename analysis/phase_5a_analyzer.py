"""
PHASE 5A DAY 1: CONTENT ANALYZER ANALYSIS REPORT

Date: August 4, 2025
Target: core/content_analyzer.py (1,834 lines)
Goal: Plan modular consolidation for 55% code reduction

=============================================================================
METHOD INVENTORY & CLASSIFICATION
=============================================================================
"""

import re
from pathlib import Path

def analyze_content_analyzer():
    """Analyze the content analyzer file structure."""
    
    # Read the file
    content_analyzer_path = Path("c:/Temp/openchronicle-core/core/content_analyzer.py")
    with open(content_analyzer_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract method definitions
    method_pattern = r'^\s*(async def|def)\s+(\w+)\(.*?\):'
    methods = re.findall(method_pattern, content, re.MULTILINE)
    
    print(f"CONTENT ANALYZER METHOD INVENTORY")
    print(f"={'='*50}")
    print(f"Total file size: {len(content.splitlines())} lines")
    print(f"Total methods found: {len(methods)}")
    print(f"")
    
    # Categorize methods by functionality
    categories = {
        'Model Management': [],
        'Content Detection': [],
        'Data Extraction': [],
        'Analysis Core': [],
        'Routing & Recommendation': [],
        'Utility & Support': []
    }
    
    for method_type, method_name in methods:
        if any(keyword in method_name.lower() for keyword in ['model', 'availability', 'transformer', 'connectivity']):
            categories['Model Management'].append((method_type, method_name))
        elif any(keyword in method_name.lower() for keyword in ['detect', 'classify', 'category']):
            categories['Content Detection'].append((method_type, method_name))
        elif any(keyword in method_name.lower() for keyword in ['extract', 'character', 'location', 'lore']):
            categories['Data Extraction'].append((method_type, method_name))
        elif any(keyword in method_name.lower() for keyword in ['analyze', 'analysis', 'combine']):
            categories['Analysis Core'].append((method_type, method_name))
        elif any(keyword in method_name.lower() for keyword in ['recommend', 'routing', 'optimize', 'suggest']):
            categories['Routing & Recommendation'].append((method_type, method_name))
        else:
            categories['Utility & Support'].append((method_type, method_name))
    
    # Print categorized results
    for category, methods_list in categories.items():
        print(f"\n{category.upper()} ({len(methods_list)} methods):")
        print(f"{'-'*40}")
        for method_type, method_name in methods_list:
            print(f"  {method_type} {method_name}")
    
    print(f"\n{'='*50}")
    print(f"CONSOLIDATION OPPORTUNITIES IDENTIFIED")
    print(f"{'='*50}")
    
    consolidation_plan = {
        'detection/': ['Content Detection', 'Analysis Core (partial)'],
        'extraction/': ['Data Extraction'],  
        'routing/': ['Routing & Recommendation', 'Model Management'],
        'shared/': ['Utility & Support', 'Analysis Core (shared)']
    }
    
    for folder, target_categories in consolidation_plan.items():
        print(f"\n{folder}")
        print(f"  Target categories: {', '.join(target_categories)}")
        estimated_methods = sum(len(categories.get(cat.split(' (')[0], [])) for cat in target_categories)
        print(f"  Estimated methods: {estimated_methods}")

if __name__ == "__main__":
    analyze_content_analyzer()
