#!/usr/bin/env python3
"""
OpenChronicle Output Formatter

Focused component for formatting import results and generating reports.
Handles output generation and formatting for different purposes.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..interfaces import IOutputFormatter, ImportResult, ImportContext, ContentFile
from core.shared.logging_system import get_logger, log_system_event


class OutputFormatter(IOutputFormatter):
    """Handles formatting of import results and report generation."""
    
    def __init__(self):
        """Initialize the output formatter."""
        self.logger = get_logger()
        
        # Formatting templates
        self.formatting_options = {
            'json_indent': 2,
            'max_summary_length': 200,
            'max_error_display': 10,
            'datetime_format': '%Y-%m-%d %H:%M:%S'
        }
    
    def format_import_result(self, result: ImportResult, 
                           format_type: str = 'summary') -> str:
        """
        Format import result for display.
        
        Args:
            result: Import result to format
            format_type: Type of formatting ('summary', 'detailed', 'json')
            
        Returns:
            Formatted string representation
        """
        try:
            if format_type == 'summary':
                return self._format_summary(result)
            elif format_type == 'detailed':
                return self._format_detailed(result)
            elif format_type == 'json':
                return self._format_json(result)
            else:
                self.logger.warning(f"Unknown format type: {format_type}, using summary")
                return self._format_summary(result)
                
        except Exception as e:
            self.logger.error(f"Failed to format import result: {e}")
            return f"Error formatting result: {e}"
    
    def generate_report(self, result: ImportResult, 
                       report_type: str = 'standard') -> Dict[str, Any]:
        """
        Generate comprehensive import report.
        
        Args:
            result: Import result to generate report for
            report_type: Type of report ('standard', 'technical', 'executive')
            
        Returns:
            Structured report data
        """
        try:
            base_report = self._create_base_report(result)
            
            if report_type == 'standard':
                return self._enhance_standard_report(base_report, result)
            elif report_type == 'technical':
                return self._enhance_technical_report(base_report, result)
            elif report_type == 'executive':
                return self._enhance_executive_report(base_report, result)
            else:
                self.logger.warning(f"Unknown report type: {report_type}, using standard")
                return self._enhance_standard_report(base_report, result)
                
        except Exception as e:
            self.logger.error(f"Failed to generate report: {e}")
            return self._create_error_report(e, result)
    
    def save_report(self, report: Dict[str, Any], output_path: Path, 
                   format_type: str = 'json') -> bool:
        """
        Save report to file.
        
        Args:
            report: Report data to save
            output_path: Path where to save the report
            format_type: Format to save ('json', 'txt', 'html')
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if format_type == 'json':
                return self._save_json_report(report, output_path)
            elif format_type == 'txt':
                return self._save_text_report(report, output_path)
            elif format_type == 'html':
                return self._save_html_report(report, output_path)
            else:
                self.logger.error(f"Unsupported format type: {format_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to save report to {output_path}: {e}")
            return False
    
    def format_import_summary(self, result: ImportResult) -> str:
        """Format import results for display."""
        return self.format_import_result(result, 'summary')
    
    def generate_readme(self, context: ImportContext, content_summary: Dict[str, Any]) -> str:
        """Generate README content for the storypack."""
        readme_lines = [
            f"# {context.storypack_name}",
            "",
            "This storypack was generated using OpenChronicle's modular import system.",
            "",
            "## Content Summary",
            f"- **Files Processed**: {content_summary.get('total_files', 0)}",
            f"- **Import Mode**: {context.import_mode}",
            f"- **AI Processing**: {'Enabled' if context.ai_available else 'Disabled'}",
            "",
            "## Content Categories"
        ]
        
        files_by_category = content_summary.get('files_by_category', {})
        for category, files in files_by_category.items():
            readme_lines.append(f"- **{category.title()}**: {len(files)} files")
        
        readme_lines.extend([
            "",
            "## Import Details",
            f"- **Source**: {context.source_path}",
            f"- **Created**: {context.target_path.stat().st_ctime if context.target_path.exists() else 'N/A'}",
            "",
            "---",
            "*Generated by OpenChronicle Storypack Import System*"
        ])
        
        return "\n".join(readme_lines)
    
    def format_error_report(self, errors: List[str], warnings: List[str]) -> str:
        """Format error and warning messages."""
        report_lines = []
        
        if errors:
            report_lines.append("## Errors")
            for i, error in enumerate(errors, 1):
                report_lines.append(f"{i}. {error}")
            report_lines.append("")
        
        if warnings:
            report_lines.append("## Warnings")
            for i, warning in enumerate(warnings, 1):
                report_lines.append(f"{i}. {warning}")
            report_lines.append("")
        
        if not errors and not warnings:
            report_lines.append("No errors or warnings to report.")
        
        return "\n".join(report_lines)

    def _format_summary(self, result: ImportResult) -> str:
        """Format a concise summary of the import result."""
        status = "✅ SUCCESS" if result.success else "❌ FAILED"
        
        summary_lines = [
            f"Import Status: {status}",
            f"Storypack: {result.storypack_name}",
            f"Files Processed: {result.files_processed}",
            f"Processing Time: {result.processing_time:.2f}s"
        ]
        
        if result.errors:
            error_count = len(result.errors)
            summary_lines.append(f"Errors: {error_count}")
            
            # Show first few errors
            for i, error in enumerate(result.errors[:3]):
                summary_lines.append(f"  - {error}")
            
            if error_count > 3:
                summary_lines.append(f"  ... and {error_count - 3} more errors")
        
        if result.warnings:
            warning_count = len(result.warnings)
            summary_lines.append(f"Warnings: {warning_count}")
        
        return "\n".join(summary_lines)
    
    def _format_detailed(self, result: ImportResult) -> str:
        """Format a detailed view of the import result."""
        sections = []
        
        # Header
        status = "SUCCESS" if result.success else "FAILED"
        sections.append(f"=== IMPORT RESULT: {status} ===")
        sections.append(f"Storypack: {result.storypack_name}")
        sections.append(f"Created At: {result.created_at}")
        sections.append(f"Processing Time: {result.processing_time:.2f} seconds")
        sections.append("")
        
        # File processing details
        sections.append("=== FILE PROCESSING ===")
        sections.append(f"Total Files Processed: {result.files_processed}")
        
        if result.metadata.get('files_by_category'):
            sections.append("\nFiles by Category:")
            for category, files in result.metadata['files_by_category'].items():
                sections.append(f"  {category}: {len(files)}")
        
        # Generated files
        if result.generated_files:
            sections.append(f"\nGenerated Files: {len(result.generated_files)}")
            for file_path in result.generated_files[:10]:  # Show first 10
                sections.append(f"  - {file_path}")
            if len(result.generated_files) > 10:
                sections.append(f"  ... and {len(result.generated_files) - 10} more files")
        
        # Errors section
        if result.errors:
            sections.append(f"\n=== ERRORS ({len(result.errors)}) ===")
            for i, error in enumerate(result.errors[:self.formatting_options['max_error_display']]):
                sections.append(f"{i+1}. {error}")
            
            if len(result.errors) > self.formatting_options['max_error_display']:
                remaining = len(result.errors) - self.formatting_options['max_error_display']
                sections.append(f"... and {remaining} more errors")
        
        # Warnings section
        if result.warnings:
            sections.append(f"\n=== WARNINGS ({len(result.warnings)}) ===")
            for warning in result.warnings[:5]:  # Show first 5 warnings
                sections.append(f"- {warning}")
            
            if len(result.warnings) > 5:
                sections.append(f"... and {len(result.warnings) - 5} more warnings")
        
        # Additional metadata
        if result.metadata:
            sections.append("\n=== METADATA ===")
            for key, value in result.metadata.items():
                if key not in ['files_by_category']:  # Skip already displayed
                    if isinstance(value, (dict, list)):
                        sections.append(f"{key}: {type(value).__name__} with {len(value)} items")
                    else:
                        value_str = str(value)
                        if len(value_str) > self.formatting_options['max_summary_length']:
                            value_str = value_str[:self.formatting_options['max_summary_length']] + "..."
                        sections.append(f"{key}: {value_str}")
        
        return "\n".join(sections)
    
    def _format_json(self, result: ImportResult) -> str:
        """Format result as JSON."""
        # Convert ImportResult to dict for JSON serialization
        result_dict = {
            'success': result.success,
            'storypack_name': result.storypack_name,
            'storypack_path': str(result.storypack_path) if result.storypack_path else None,
            'files_processed': result.files_processed,
            'generated_files': [str(f) for f in result.generated_files],
            'processing_time': result.processing_time,
            'created_at': result.created_at,
            'errors': result.errors,
            'warnings': result.warnings,
            'metadata': result.metadata
        }
        
        return json.dumps(result_dict, indent=self.formatting_options['json_indent'])
    
    def _create_base_report(self, result: ImportResult) -> Dict[str, Any]:
        """Create base report structure."""
        return {
            'report_info': {
                'generated_at': datetime.now().strftime(self.formatting_options['datetime_format']),
                'report_version': '1.0',
                'openchronicle_version': 'current'  # Would be filled from actual version
            },
            'import_summary': {
                'success': result.success,
                'storypack_name': result.storypack_name,
                'storypack_path': str(result.storypack_path) if result.storypack_path else None,
                'files_processed': result.files_processed,
                'processing_time': result.processing_time,
                'created_at': result.created_at
            },
            'results': {
                'generated_files_count': len(result.generated_files),
                'errors_count': len(result.errors),
                'warnings_count': len(result.warnings)
            }
        }
    
    def _enhance_standard_report(self, base_report: Dict[str, Any], 
                               result: ImportResult) -> Dict[str, Any]:
        """Enhance report with standard details."""
        report = base_report.copy()
        
        # Add file details
        report['file_processing'] = {
            'generated_files': [str(f) for f in result.generated_files],
            'files_by_category': result.metadata.get('files_by_category', {})
        }
        
        # Add issues
        if result.errors:
            report['issues'] = {
                'errors': result.errors,
                'warnings': result.warnings
            }
        
        # Add key metadata
        if result.metadata:
            report['import_details'] = {
                key: value for key, value in result.metadata.items()
                if key not in ['files_by_category']
            }
        
        return report
    
    def _enhance_technical_report(self, base_report: Dict[str, Any], 
                                result: ImportResult) -> Dict[str, Any]:
        """Enhance report with technical details."""
        report = self._enhance_standard_report(base_report, result)
        
        # Add technical metrics
        report['technical_metrics'] = {
            'processing_efficiency': result.files_processed / max(result.processing_time, 0.001),
            'error_rate': len(result.errors) / max(result.files_processed, 1),
            'success_rate': 1.0 if result.success else 0.0
        }
        
        # Add detailed metadata
        report['technical_details'] = result.metadata
        
        # Add system information (would be enhanced with actual system data)
        report['system_info'] = {
            'platform': 'windows',  # Would be detected
            'python_version': 'current',  # Would be detected
            'memory_usage': 'not_tracked',  # Would be implemented
            'disk_usage': 'not_tracked'  # Would be implemented
        }
        
        return report
    
    def _enhance_executive_report(self, base_report: Dict[str, Any], 
                                result: ImportResult) -> Dict[str, Any]:
        """Enhance report with executive summary."""
        report = base_report.copy()
        
        # Executive summary
        report['executive_summary'] = {
            'status': 'Completed Successfully' if result.success else 'Completed with Issues',
            'key_metrics': {
                'files_imported': result.files_processed,
                'time_taken': f"{result.processing_time:.1f} seconds",
                'issues_found': len(result.errors) + len(result.warnings)
            },
            'recommendations': self._generate_recommendations(result)
        }
        
        # High-level statistics
        report['statistics'] = {
            'content_categories': len(result.metadata.get('files_by_category', {})),
            'success_rate': '100%' if result.success else f"{((result.files_processed - len(result.errors)) / max(result.files_processed, 1) * 100):.1f}%"
        }
        
        return report
    
    def _generate_recommendations(self, result: ImportResult) -> List[str]:
        """Generate recommendations based on import results."""
        recommendations = []
        
        if result.errors:
            recommendations.append("Review and address import errors before using the storypack")
        
        if result.warnings:
            recommendations.append("Consider addressing warnings to improve content quality")
        
        if result.files_processed > 100:
            recommendations.append("Large import completed - consider organizing content into subcategories")
        
        if result.processing_time > 60:
            recommendations.append("Long processing time - consider using AI processing for better efficiency")
        
        if not recommendations:
            recommendations.append("Import completed successfully - storypack is ready for use")
        
        return recommendations
    
    def _create_error_report(self, error: Exception, result: ImportResult) -> Dict[str, Any]:
        """Create error report when report generation fails."""
        return {
            'report_info': {
                'generated_at': datetime.now().strftime(self.formatting_options['datetime_format']),
                'status': 'error',
                'error': str(error)
            },
            'import_summary': {
                'success': False,
                'storypack_name': result.storypack_name if result else 'unknown',
                'error_message': f"Report generation failed: {error}"
            }
        }
    
    def _save_json_report(self, report: Dict[str, Any], output_path: Path) -> bool:
        """Save report as JSON."""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=self.formatting_options['json_indent'])
            
            log_system_event("output_formatter", "JSON report saved", {
                "output_path": str(output_path),
                "report_sections": list(report.keys())
            })
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save JSON report: {e}")
            return False
    
    def _save_text_report(self, report: Dict[str, Any], output_path: Path) -> bool:
        """Save report as text."""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(self._convert_report_to_text(report))
            
            log_system_event("output_formatter", "Text report saved", {
                "output_path": str(output_path)
            })
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save text report: {e}")
            return False
    
    def _save_html_report(self, report: Dict[str, Any], output_path: Path) -> bool:
        """Save report as HTML."""
        try:
            html_content = self._convert_report_to_html(report)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            log_system_event("output_formatter", "HTML report saved", {
                "output_path": str(output_path)
            })
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save HTML report: {e}")
            return False
    
    def _convert_report_to_text(self, report: Dict[str, Any]) -> str:
        """Convert report to plain text format."""
        lines = []
        
        # Title
        lines.append("OpenChronicle Import Report")
        lines.append("=" * 50)
        lines.append("")
        
        # Recursively format the report
        self._format_dict_to_text(report, lines, 0)
        
        return "\n".join(lines)
    
    def _format_dict_to_text(self, data: Any, lines: List[str], indent: int = 0):
        """Recursively format dictionary to text lines."""
        prefix = "  " * indent
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    lines.append(f"{prefix}{key}:")
                    self._format_dict_to_text(value, lines, indent + 1)
                else:
                    lines.append(f"{prefix}{key}: {value}")
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)):
                    lines.append(f"{prefix}[{i}]:")
                    self._format_dict_to_text(item, lines, indent + 1)
                else:
                    lines.append(f"{prefix}- {item}")
    
    def _convert_report_to_html(self, report: Dict[str, Any]) -> str:
        """Convert report to HTML format."""
        html = """<!DOCTYPE html>
<html>
<head>
    <title>OpenChronicle Import Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        .section { margin: 20px 0; }
        .success { color: #27ae60; }
        .error { color: #e74c3c; }
        .warning { color: #f39c12; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <div class="header">
        <h1>OpenChronicle Import Report</h1>
    </div>
"""
        
        # Add report content (simplified version)
        if 'import_summary' in report:
            summary = report['import_summary']
            status_class = 'success' if summary.get('success') else 'error'
            
            html += f"""
    <div class="section">
        <h2>Import Summary</h2>
        <p><strong>Status:</strong> <span class="{status_class}">
        {'SUCCESS' if summary.get('success') else 'FAILED'}</span></p>
        <p><strong>Storypack:</strong> {summary.get('storypack_name', 'Unknown')}</p>
        <p><strong>Files Processed:</strong> {summary.get('files_processed', 0)}</p>
        <p><strong>Processing Time:</strong> {summary.get('processing_time', 0):.2f} seconds</p>
    </div>
"""
        
        html += """
</body>
</html>"""
        
        return html
