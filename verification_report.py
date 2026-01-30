#!/usr/bin/env python3
"""
Post-Run Verification Report
Checks all generated projects on Desktop for enterprise-grade quality
Can also verify single projects for QA
"""

import os
import sys
import json
from pathlib import Path

def check_project_quality(project_path):
    """Check if project meets enterprise-grade standards"""
    checks = {
        'has_main_file': False,
        'has_readme': False,
        'has_metadata': False,
        'code_size': 0,
        'has_classes': False,
        'has_functions': False,
        'has_docstrings': False,
        'has_error_handling': False,
        'has_main_block': False,
        'status': 'unknown',
        'qa_score': 0
    }
    
    # Check for main Python file
    main_file = project_path / 'main.py'
    if main_file.exists():
        checks['has_main_file'] = True
        code = main_file.read_text()
        checks['code_size'] = len(code)
        checks['has_classes'] = 'class ' in code
        checks['has_functions'] = 'def ' in code
        checks['has_docstrings'] = '"""' in code or "'''" in code
        checks['has_error_handling'] = 'try:' in code or 'except' in code
        checks['has_main_block'] = 'if __name__ == "__main__":' in code
    
    # Check for README
    readme = project_path / 'README.md'
    if readme.exists():
        checks['has_readme'] = True
    
    # Check for metadata
    metadata_file = project_path / 'project_metadata.json'
    if metadata_file.exists():
        checks['has_metadata'] = True
        try:
            metadata = json.loads(metadata_file.read_text())
            checks['status'] = metadata.get('status', 'unknown')
            checks['qa_score'] = metadata.get('qa_score', 0)
        except:
            pass
    
    return checks

def verify_single_project(project_path):
    """Verify a single project and print detailed report."""
    project = Path(project_path)
    if not project.exists():
        print(f"Error: Project not found: {project_path}")
        return False
    
    print("=" * 80)
    print(f"SINGLE PROJECT VERIFICATION: {project.name}")
    print("=" * 80)
    
    checks = check_project_quality(project)
    
    print("\nQuality Checks:")
    print(f"  Main file:        {'✓' if checks['has_main_file'] else '✗'}")
    print(f"  README:           {'✓' if checks['has_readme'] else '✗'}")
    print(f"  Metadata:         {'✓' if checks['has_metadata'] else '✗'}")
    print(f"  Code size:        {checks['code_size']:,} chars")
    print(f"  Classes:          {'✓' if checks['has_classes'] else '✗'}")
    print(f"  Functions:        {'✓' if checks['has_functions'] else '✗'}")
    print(f"  Docstrings:       {'✓' if checks['has_docstrings'] else '✗'}")
    print(f"  Error handling:   {'✓' if checks['has_error_handling'] else '✗'}")
    print(f"  Main block:       {'✓' if checks['has_main_block'] else '✗'}")
    print(f"  Status:           {checks['status']}")
    print(f"  QA Score:         {checks['qa_score']}/100")
    
    # Check enterprise criteria
    enterprise_pass = all([
        checks['has_classes'],
        checks['has_functions'],
        checks['has_error_handling'],
        checks['has_docstrings'],
        checks['code_size'] >= 5000
    ])
    
    print("\n" + "=" * 80)
    if enterprise_pass:
        print("RESULT: ✓ PASSES ENTERPRISE-GRADE STANDARDS")
    else:
        print("RESULT: ✗ DOES NOT MEET ENTERPRISE-GRADE STANDARDS")
        print("\nIssues:")
        if not checks['has_classes']:
            print("  - Missing classes")
        if not checks['has_functions']:
            print("  - Missing functions")
        if not checks['has_error_handling']:
            print("  - Missing error handling")
        if not checks['has_docstrings']:
            print("  - Missing docstrings")
        if checks['code_size'] < 5000:
            print(f"  - Code size too small ({checks['code_size']} < 5000)")
    print("=" * 80)
    
    return enterprise_pass

def main():
    # Check if single project verification requested
    if len(sys.argv) > 1:
        project_path = sys.argv[1]
        verify_single_project(project_path)
        return
    
    # Otherwise, run batch verification on Desktop
    desktop = Path('/home/pi/Desktop')
    
    # Exclude test and game folders
    exclude = {'test', 'game'}
    
    # Find all project folders
    projects = [p for p in desktop.iterdir() 
                if p.is_dir() and p.name not in exclude]
    
    print("=" * 80)
    print("POST-RUN VERIFICATION REPORT")
    print("=" * 80)
    print(f"\nTotal projects found: {len(projects)}")
    print(f"Desktop path: {desktop}")
    
    # Analyze each project
    results = []
    for project in sorted(projects):
        checks = check_project_quality(project)
        results.append({
            'name': project.name,
            'checks': checks
        })
    
    # Summary statistics
    completed = sum(1 for r in results if r['checks']['status'] == 'completed')
    in_progress = sum(1 for r in results if r['checks']['status'] == 'in_progress')
    with_classes = sum(1 for r in results if r['checks']['has_classes'])
    with_functions = sum(1 for r in results if r['checks']['has_functions'])
    with_error_handling = sum(1 for r in results if r['checks']['has_error_handling'])
    with_docstrings = sum(1 for r in results if r['checks']['has_docstrings'])
    avg_code_size = sum(r['checks']['code_size'] for r in results) / len(results) if results else 0
    avg_qa_score = sum(r['checks']['qa_score'] for r in results if r['checks']['qa_score'] > 0)
    qa_count = sum(1 for r in results if r['checks']['qa_score'] > 0)
    avg_qa_score = avg_qa_score / qa_count if qa_count > 0 else 0
    
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print(f"Completed projects:        {completed}/{len(results)} ({completed/len(results)*100:.1f}%)")
    print(f"In-progress projects:      {in_progress}/{len(results)}")
    print(f"Projects with classes:     {with_classes}/{len(results)} ({with_classes/len(results)*100:.1f}%)")
    print(f"Projects with functions:   {with_functions}/{len(results)} ({with_functions/len(results)*100:.1f}%)")
    print(f"Projects with error handling: {with_error_handling}/{len(results)} ({with_error_handling/len(results)*100:.1f}%)")
    print(f"Projects with docstrings:  {with_docstrings}/{len(results)} ({with_docstrings/len(results)*100:.1f}%)")
    print(f"Average code size:         {avg_code_size:,.0f} characters")
    if qa_count > 0:
        print(f"Average QA score:          {avg_qa_score:.1f}/100 (from {qa_count} projects)")
    
    # Enterprise-grade standards
    print("\n" + "=" * 80)
    print("ENTERPRISE-GRADE STANDARDS CHECK")
    print("=" * 80)
    
    enterprise_criteria = {
        'Classes': with_classes / len(results) >= 0.8,
        'Functions': with_functions / len(results) >= 0.95,
        'Error Handling': with_error_handling / len(results) >= 0.7,
        'Docstrings': with_docstrings / len(results) >= 0.8,
        'Avg Code Size >= 5000': avg_code_size >= 5000,
        'Completion Rate >= 80%': completed / len(results) >= 0.8
    }
    
    for criterion, passed in enterprise_criteria.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {criterion}")
    
    # Detailed project listing (first 10)
    print("\n" + "=" * 80)
    print("DETAILED PROJECT LISTING (First 10)")
    print("=" * 80)
    
    for i, result in enumerate(results[:10], 1):
        name = result['name']
        checks = result['checks']
        print(f"\n{i}. {name}")
        print(f"   Status: {checks['status']}")
        print(f"   Code size: {checks['code_size']:,} chars")
        print(f"   Classes: {'✓' if checks['has_classes'] else '✗'} | "
              f"Functions: {'✓' if checks['has_functions'] else '✗'} | "
              f"Error handling: {'✓' if checks['has_error_handling'] else '✗'} | "
              f"Docstrings: {'✓' if checks['has_docstrings'] else '✗'}")
    
    # Quality score calculation
    print("\n" + "=" * 80)
    print("OVERALL QUALITY SCORE")
    print("=" * 80)
    
    quality_scores = []
    for result in results:
        c = result['checks']
        score = 0
        score += 20 if c['has_main_file'] else 0
        score += 10 if c['has_readme'] else 0
        score += 10 if c['has_metadata'] else 0
        score += 15 if c['has_classes'] else 0
        score += 15 if c['has_functions'] else 0
        score += 10 if c['has_docstrings'] else 0
        score += 10 if c['has_error_handling'] else 0
        score += 10 if c['has_main_block'] else 0
        quality_scores.append(score)
    
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
    
    print(f"Average Quality Score: {avg_quality:.1f}/100")
    
    if avg_quality >= 80:
        print("🏆 EXCELLENT - Enterprise-grade quality achieved!")
    elif avg_quality >= 60:
        print("✅ GOOD - Meets basic enterprise standards")
    elif avg_quality >= 40:
        print("⚠️  FAIR - Needs improvement for enterprise standards")
    else:
        print("❌ POOR - Does not meet enterprise standards")
    
    # Final recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    if with_classes / len(results) < 0.8:
        print("• Increase class usage - aim for 80%+ projects with classes")
    if with_error_handling / len(results) < 0.7:
        print("• Add more error handling - aim for 70%+ projects with try/except")
    if with_docstrings / len(results) < 0.8:
        print("• Improve documentation - aim for 80%+ projects with docstrings")
    if avg_code_size < 5000:
        print(f"• Increase code depth - current avg {avg_code_size:.0f} chars, target 5000+")
    if completed / len(results) < 0.8:
        print("• Improve completion rate - aim for 80%+ completed projects")
    
    if all(enterprise_criteria.values()):
        print("\n✅ All enterprise-grade criteria met!")
    else:
        print(f"\n⚠️  {sum(enterprise_criteria.values())}/{len(enterprise_criteria)} criteria met")
    
    print("\n" + "=" * 80)
    
    return 0 if avg_quality >= 60 else 1

if __name__ == '__main__':
    sys.exit(main())
