#!/usr/bin/env python3
"""
Import Analysis Script

Analyzes current import structure in OpenChronicle to plan
the architecture migration strategy.

Usage:
    python scripts/import_analysis.py
"""

import ast
import sys
import json
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
from collections import defaultdict, Counter
from datetime import datetime


class ImportVisitor(ast.NodeVisitor):
    """AST visitor to extract import information."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.imports = []
        self.from_imports = []
        self.relative_imports = []
    
    def visit_Import(self, node: ast.Import) -> None:
        """Visit import statements."""
        for alias in node.names:
            self.imports.append({
                "module": alias.name,
                "alias": alias.asname,
                "line": node.lineno
            })
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from...import statements."""
        if node.module:
            import_info = {
                "module": node.module,
                "names": [alias.name for alias in node.names],
                "aliases": {alias.name: alias.asname for alias in node.names if alias.asname},
                "line": node.lineno,
                "level": node.level
            }
            
            if node.level > 0:
                self.relative_imports.append(import_info)
            else:
                self.from_imports.append(import_info)


def analyze_file_imports(file_path: Path) -> Dict[str, Any]:
    """Analyze imports in a single Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=str(file_path))
        visitor = ImportVisitor(file_path)
        visitor.visit(tree)
        
        return {
            "file": str(file_path),
            "imports": visitor.imports,
            "from_imports": visitor.from_imports,
            "relative_imports": visitor.relative_imports,
            "line_count": len(content.splitlines()),
            "success": True
        }
    
    except Exception as e:
        return {
            "file": str(file_path),
            "error": str(e),
            "success": False
        }


def find_python_files(root_dir: Path) -> List[Path]:
    """Find all Python files in the project."""
    python_files = []
    
    # Include main source areas
    search_patterns = [
        "src/**/*.py",
        "core/**/*.py", 
        "utilities/**/*.py",
        "api/**/*.py",
        "cli/**/*.py",
        "tests/**/*.py",
        "*.py"  # Root level files
    ]
    
    for pattern in search_patterns:
        python_files.extend(root_dir.glob(pattern))
    
    # Remove duplicates and __pycache__ files
    unique_files = []
    seen = set()
    
    for file_path in python_files:
        if "__pycache__" in str(file_path):
            continue
        if file_path.resolve() not in seen:
            seen.add(file_path.resolve())
            unique_files.append(file_path)
    
    return sorted(unique_files)


def categorize_imports(import_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Categorize and analyze import patterns."""
    categories = {
        "standard_library": set(),
        "third_party": set(),
        "openchronicle_internal": set(),
        "core_legacy": set(),
        "utilities": set(),
        "relative": set(),
        "unknown": set()
    }
    
    import_counts = Counter()
    file_import_counts = defaultdict(int)
    problematic_imports = []
    
    for file_data in import_data:
        if not file_data["success"]:
            continue
        
        file_path = file_data["file"]
        
        # Process all import types
        all_imports = []
        all_imports.extend(file_data["imports"])
        all_imports.extend(file_data["from_imports"])
        
        for imp in all_imports:
            module_name = imp["module"]
            import_counts[module_name] += 1
            file_import_counts[file_path] += 1
            
            # Categorize the import
            if _is_standard_library(module_name):
                categories["standard_library"].add(module_name)
            elif _is_third_party(module_name):
                categories["third_party"].add(module_name)
            elif module_name.startswith("openchronicle"):
                categories["openchronicle_internal"].add(module_name)
            elif module_name.startswith("core."):
                categories["core_legacy"].add(module_name)
                # This is problematic for hexagonal architecture
                problematic_imports.append({
                    "file": file_path,
                    "module": module_name,
                    "line": imp.get("line"),
                    "reason": "Direct core import - violates hexagonal architecture"
                })
            elif module_name.startswith("utilities"):
                categories["utilities"].add(module_name)
            else:
                categories["unknown"].add(module_name)
        
        # Process relative imports
        for rel_imp in file_data["relative_imports"]:
            level = rel_imp["level"]
            module = rel_imp.get("module", "")
            categories["relative"].add(f"{'.' * level}{module}")
            
            # Check for problematic relative imports
            if level > 2:
                problematic_imports.append({
                    "file": file_path,
                    "module": f"{'.' * level}{module}",
                    "line": rel_imp.get("line"),
                    "reason": f"Deep relative import (level {level}) - may break during migration"
                })
    
    # Convert sets to sorted lists for JSON serialization
    for category in categories:
        categories[category] = sorted(list(categories[category]))
    
    return {
        "categories": categories,
        "import_counts": dict(import_counts.most_common(50)),  # Top 50
        "file_import_counts": dict(sorted(file_import_counts.items(), key=lambda x: x[1], reverse=True)[:20]),  # Top 20
        "problematic_imports": problematic_imports
    }


def _is_standard_library(module_name: str) -> bool:
    """Check if module is part of Python standard library."""
    stdlib_modules = {
        "os", "sys", "json", "pathlib", "typing", "asyncio", "logging",
        "datetime", "time", "re", "collections", "itertools", "functools",
        "subprocess", "threading", "multiprocessing", "sqlite3", "uuid",
        "hashlib", "base64", "urllib", "http", "email", "xml", "html",
        "ast", "traceback", "warnings", "contextlib", "dataclasses",
        "enum", "abc", "copy", "pickle", "tempfile", "shutil", "glob",
        "argparse", "configparser", "csv", "io", "struct", "socket",
        "ssl", "gzip", "zipfile", "tarfile", "platform", "getpass"
    }
    
    root_module = module_name.split('.')[0]
    return root_module in stdlib_modules


def _is_third_party(module_name: str) -> bool:
    """Check if module is likely third-party."""
    known_third_party = {
        "pytest", "numpy", "pandas", "requests", "aiohttp", "fastapi",
        "pydantic", "sqlalchemy", "alembic", "click", "typer", "rich",
        "tqdm", "jinja2", "flask", "django", "celery", "redis", "docker",
        "kubernetes", "boto3", "azure", "google", "openai", "anthropic",
        "transformers", "torch", "tensorflow", "scikit-learn", "matplotlib",
        "seaborn", "plotly", "streamlit", "gradio", "langchain", "chromadb"
    }
    
    root_module = module_name.split('.')[0]
    return root_module in known_third_party


def analyze_import_dependencies() -> Dict[str, Any]:
    """Analyze import dependencies across the project."""
    project_root = Path(".")
    
    print("Analyzing OpenChronicle Import Structure")
    print("=" * 50)
    
    # Find all Python files
    print("📁 Finding Python files...")
    python_files = find_python_files(project_root)
    print(f"  Found {len(python_files)} Python files")
    
    # Analyze imports in each file
    print("📦 Analyzing imports...")
    import_data = []
    success_count = 0
    
    for i, file_path in enumerate(python_files, 1):
        if i % 50 == 0:
            print(f"  Processed {i}/{len(python_files)} files...")
        
        file_analysis = analyze_file_imports(file_path)
        import_data.append(file_analysis)
        
        if file_analysis["success"]:
            success_count += 1
    
    print(f"  Successfully analyzed {success_count}/{len(python_files)} files")
    
    # Categorize imports
    print("🏷️  Categorizing imports...")
    categorized_data = categorize_imports(import_data)
    
    # Generate summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_files": len(python_files),
        "analyzed_files": success_count,
        "import_analysis": categorized_data,
        "raw_data": import_data[:100]  # Limit raw data for file size
    }
    
    return summary


def generate_migration_recommendations(analysis: Dict[str, Any]) -> List[str]:
    """Generate migration recommendations based on import analysis."""
    recommendations = []
    categories = analysis["import_analysis"]["categories"]
    problematic = analysis["import_analysis"]["problematic_imports"]
    
    # Check for legacy core imports
    if categories["core_legacy"]:
        recommendations.append({
            "priority": "HIGH",
            "category": "Legacy Core Imports",
            "issue": f"Found {len(categories['core_legacy'])} different core.* imports",
            "action": "Replace with src.openchronicle.* imports",
            "examples": categories["core_legacy"][:5]
        })
    
    # Check for deep relative imports
    deep_relative = [p for p in problematic if "Deep relative import" in p["reason"]]
    if deep_relative:
        recommendations.append({
            "priority": "MEDIUM",
            "category": "Deep Relative Imports", 
            "issue": f"Found {len(deep_relative)} deep relative imports",
            "action": "Convert to absolute imports from src.openchronicle",
            "examples": [f"{p['file']}:{p['line']}" for p in deep_relative[:3]]
        })
    
    # Check for utilities imports
    if categories["utilities"]:
        recommendations.append({
            "priority": "MEDIUM",
            "category": "Utilities Imports",
            "issue": f"Found {len(categories['utilities'])} utilities imports",
            "action": "Move to src.openchronicle.infrastructure.utilities",
            "examples": categories["utilities"][:5]
        })
    
    # Check for unknown imports
    if categories["unknown"]:
        recommendations.append({
            "priority": "LOW",
            "category": "Unknown Imports",
            "issue": f"Found {len(categories['unknown'])} unrecognized imports",
            "action": "Review and categorize these imports",
            "examples": categories["unknown"][:5]
        })
    
    return recommendations


def main() -> int:
    """Main function."""
    try:
        # Run analysis
        analysis = analyze_import_dependencies()
        
        # Generate recommendations
        recommendations = generate_migration_recommendations(analysis)
        analysis["migration_recommendations"] = recommendations
        
        # Save results
        output_file = Path("storage/import_analysis.json")
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2)
        
        print(f"\n💾 Analysis saved to: {output_file}")
        
        # Print summary
        print("\n" + "=" * 50)
        print("📊 Import Analysis Summary")
        print("=" * 50)
        
        categories = analysis["import_analysis"]["categories"]
        for category, imports in categories.items():
            if imports:
                print(f"🏷️  {category.replace('_', ' ').title()}: {len(imports)} imports")
        
        problematic = analysis["import_analysis"]["problematic_imports"]
        if problematic:
            print(f"\n⚠️  Problematic Imports: {len(problematic)}")
            for issue in problematic[:5]:
                file_path = Path(issue["file"]).name
                print(f"   • {file_path}:{issue['line']} - {issue['module']}")
        
        if recommendations:
            print(f"\n🔧 Migration Recommendations: {len(recommendations)}")
            for rec in recommendations:
                priority_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}[rec["priority"]]
                print(f"   {priority_icon} {rec['category']}: {rec['action']}")
        
        print("\n🎉 Import analysis complete!")
        return 0
        
    except Exception as e:
        print(f"\nError during analysis: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
