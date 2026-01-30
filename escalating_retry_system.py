#!/usr/bin/env python3
"""
Escalating Retry System with Learning Database

When a project fails 4 times:
1. Extract specific errors and code blocks
2. Check learning database for similar errors solved before
3. Try 20 variations with escalating aggressiveness:
   - Conservative (fix syntax, keep logic)
   - Moderate (rewrite section)
   - Aggressive (different approach)
   - Nuclear (start from scratch)
4. Save working fix to database for future reuse

The database grows smarter over time!
"""

import json
from pathlib import Path
from datetime import datetime
import hashlib

class LearningFixDatabase:
    """Database of fixes learned from solving failures"""
    
    def __init__(self):
        self.db_path = Path('implementation_outputs/fix_database.json')
        self.db = self._load_db()
    
    def _load_db(self):
        """Load or create the fix database"""
        if self.db_path.exists():
            try:
                with open(self.db_path) as f:
                    return json.load(f)
            except:
                return self._create_empty_db()
        return self._create_empty_db()
    
    def _create_empty_db(self):
        """Create empty database structure"""
        return {
            'metadata': {
                'created': datetime.now().isoformat(),
                'version': '1.0',
                'total_fixes': 0,
                'reuse_rate': 0.0,
                'learning_efficiency': 0.0
            },
            'error_signatures': {},  # Hash of error -> list of fixes
            'fixes_by_type': {
                'syntax': [],
                'runtime': [],
                'logic': [],
                'missing_imports': [],
                'compilation': [],
                'structure': []
            },
            'successful_patterns': {}  # Pattern name -> solution
        }
    
    def _save_db(self):
        """Save database to file"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.db_path, 'w') as f:
            json.dump(self.db, f, indent=2)
    
    def get_error_signature(self, error_message: str) -> str:
        """Create hash of error for deduplication"""
        # Take first 100 chars, hash it
        simplified = error_message[:100].strip()
        return hashlib.md5(simplified.encode()).hexdigest()[:8]
    
    def find_similar_fixes(self, error_message: str, error_type: str):
        """Find previously solved similar errors"""
        signature = self.get_error_signature(error_message)
        
        # Check by signature
        if signature in self.db['error_signatures']:
            return self.db['error_signatures'][signature]
        
        # Check by error type
        if error_type in self.db['fixes_by_type']:
            return self.db['fixes_by_type'][error_type][:3]  # Top 3
        
        return []
    
    def log_successful_fix(self, error_type: str, error_message: str, fix: str, language: str):
        """Log a successful fix for future reuse"""
        signature = self.get_error_signature(error_message)
        
        fix_entry = {
            'error_message': error_message[:200],
            'fix': fix[:500],  # Store first 500 chars
            'language': language,
            'timestamp': datetime.now().isoformat(),
            'success_count': 1
        }
        
        # Add to signature map
        if signature not in self.db['error_signatures']:
            self.db['error_signatures'][signature] = []
        self.db['error_signatures'][signature].append(fix_entry)
        
        # Add to type map
        if error_type not in self.db['fixes_by_type']:
            self.db['fixes_by_type'][error_type] = []
        self.db['fixes_by_type'][error_type].append(fix_entry)
        
        # Update stats
        self.db['metadata']['total_fixes'] += 1
        self._save_db()
        
        return True
    
    def get_reuse_rate(self):
        """Calculate reuse rate"""
        total_fixes = self.db['metadata']['total_fixes']
        if total_fixes == 0:
            return 0.0
        
        # Count how many fixes have been reused (success_count > 1)
        reused = sum(
            1 for error_type_fixes in self.db['fixes_by_type'].values()
            for fix in error_type_fixes
            if fix.get('success_count', 1) > 1
        )
        
        return (reused / total_fixes * 100) if total_fixes > 0 else 0.0
    
    def get_stats(self):
        """Get database statistics"""
        return {
            'total_fixes': self.db['metadata']['total_fixes'],
            'reuse_rate': self.get_reuse_rate(),
            'error_types_tracked': len(self.db['fixes_by_type']),
            'unique_error_signatures': len(self.db['error_signatures'])
        }


class EscalatingRetryStrategy:
    """20 variations with escalating aggressiveness"""
    
    def __init__(self, error_type: str, error_message: str, code: str, language: str):
        self.error_type = error_type
        self.error_message = error_message
        self.code = code
        self.language = language
        self.db = LearningFixDatabase()
    
    def generate_prompts(self):
        """Generate 20 prompts with escalating aggressiveness"""
        
        # Check database for similar fixes first
        similar_fixes = self.db.find_similar_fixes(self.error_message, self.error_type)
        similar_context = ""
        if similar_fixes:
            similar_context = f"\n\nPreviously solved similar error:\n{similar_fixes[0]['fix'][:200]}"
        
        prompts = []
        
        # LEVEL 1-5: CONSERVATIVE (Keep existing logic, fix syntax/imports)
        prompts.append({
            'level': 1,
            'aggressiveness': 'conservative',
            'prompt': f"""Fix only the {self.error_type} error in this {self.language} code.
            
Error: {self.error_message[:200]}

Code:
{self.code}

Keep the existing logic and structure. Only fix the specific error.{similar_context}
Return only fixed code:"""
        })
        
        prompts.append({
            'level': 2,
            'aggressiveness': 'conservative',
            'prompt': f"""Add missing imports and fix syntax errors in this {self.language} code.

Error: {self.error_type}

Code:
{self.code}

Add ALL required imports at the top. Keep the rest unchanged.
Return only code:"""
        })
        
        prompts.append({
            'level': 3,
            'aggressiveness': 'conservative',
            'prompt': f"""Debug this {self.language} code to fix the {self.error_type} error.

Error: {self.error_message[:100]}

Code:
{self.code}

Add error handling and logging. Keep main logic intact.
Return only code:"""
        })
        
        prompts.append({
            'level': 4,
            'aggressiveness': 'conservative',
            'prompt': f"""Fix the {self.error_type} error and add validation to this {self.language} code:

Code:
{self.code}

Add input validation and error checks. Preserve the structure.
Return only code:"""
        })
        
        prompts.append({
            'level': 5,
            'aggressiveness': 'conservative',
            'prompt': f"""Refactor this broken {self.language} code to fix the {self.error_type} error:

Code:
{self.code}

Improve code structure and readability while fixing the error.
Return only code:"""
        })
        
        # LEVEL 6-10: MODERATE (Rewrite problem sections)
        prompts.append({
            'level': 6,
            'aggressiveness': 'moderate',
            'prompt': f"""Rewrite the problematic section causing the {self.error_type} error:

Original code:
{self.code}

Rewrite just the broken part with a better approach.
Return only code:"""
        })
        
        prompts.append({
            'level': 7,
            'aggressiveness': 'moderate',
            'prompt': f"""Fix the {self.error_type} error with a simpler approach:

Code:
{self.code}

Simplify the implementation while fixing the error.
Return only code:"""
        })
        
        prompts.append({
            'level': 8,
            'aggressiveness': 'moderate',
            'prompt': f"""Completely rewrite this {self.language} function to fix the {self.error_type} error:

Current code:
{self.code}

Implement it differently from scratch (but keep same input/output).
Return only code:"""
        })
        
        prompts.append({
            'level': 9,
            'aggressiveness': 'moderate',
            'prompt': f"""Fix the {self.error_type} error by breaking into smaller functions:

Code:
{self.code}

Refactor into helper functions and fix the error.
Return only code:"""
        })
        
        prompts.append({
            'level': 10,
            'aggressiveness': 'moderate',
            'prompt': f"""Use a completely different algorithm to fix the {self.error_type} error:

Original approach:
{self.code}

Try a different algorithm/pattern.
Return only code:"""
        })
        
        # LEVEL 11-15: AGGRESSIVE (Different approach, rethink design)
        prompts.append({
            'level': 11,
            'aggressiveness': 'aggressive',
            'prompt': f"""Redesign this {self.language} code from scratch fixing the {self.error_type}:

{self.code}

Use a completely different design pattern.
Return only code:"""
        })
        
        for i in range(12, 16):
            prompts.append({
                'level': i,
                'aggressiveness': 'aggressive',
                'prompt': f"""Aggressive fix #{i-11}: Reimplement this {self.language} code eliminating the {self.error_type} error with approach #{i-11}:

{self.code}

Approach: Use async/parallel, caching, memoization, or state machine pattern.
Return only code:"""
            })
        
        # LEVEL 16-20: NUCLEAR (Start from scratch)
        prompts.append({
            'level': 16,
            'aggressiveness': 'nuclear',
            'prompt': f"""NUCLEAR FIX: Completely rewrite this {self.language} code from first principles.

Original (broken):
{self.code}

Ignore the original implementation. Write the simplest possible version that works.
Return only code:"""
        })
        
        for i in range(17, 21):
            prompts.append({
                'level': i,
                'aggressiveness': 'nuclear',
                'prompt': f"""FINAL ATTEMPT #{i-15}: Start completely from scratch for a {self.language} implementation.

Original error type: {self.error_type}

Write the minimal viable implementation that solves the core problem.
Return only code:"""
            })
        
        return prompts


def escalate_retry_for_project(project_name: str, errors: list, idea: dict, learning_db: 'LearningFixDatabase'):
    """
    Escalate retry strategy for a failing project using the learning database.
    Generates multiple retry ideas with escalating aggressiveness (Conservative → Nuclear).
    
    Args:
        project_name: Project being retried
        errors: List of error messages or error dicts
        idea: Original idea/project dict with title, description, code
        learning_db: Learning database to check for similar fixes
    
    Returns:
        List of escalated retry ideas with different aggressiveness levels
    """
    
    if not errors:
        errors = []
    
    # Parse error information
    error_text = ""
    error_type = "UnknownError"
    
    if isinstance(errors, list):
        if errors and isinstance(errors[0], dict):
            # List of error dicts
            error_text = " | ".join([e.get('error_message', str(e)) for e in errors])
            error_type = errors[0].get('error_type', 'UnknownError')
        else:
            # List of strings - try to extract error type
            error_messages = [str(e) for e in errors if e]
            error_text = " | ".join(error_messages)
            # Extract error type from first error message (e.g., "ModuleNotFoundError: ...")
            if error_messages and ':' in error_messages[0]:
                error_type = error_messages[0].split(':')[0].strip()
    else:
        error_text = str(errors)
    
    # Check if we have similar fixes in the learning database
    similar_fixes = learning_db.find_similar_fixes(error_text, error_type) if error_text else []
    reuse_rate = learning_db.db['metadata'].get('reuse_rate', 0)
    
    # Generate escalated retry ideas with different aggressiveness levels
    # Reduced from 20 to 8 variations to prevent queue flooding
    escalated_ideas = []
    levels = ['Conservative', 'Moderate', 'Aggressive', 'Nuclear']
    
    for level_idx, level in enumerate(levels):
        for variation in range(2):  # 2 variations per level = 8 total
            escalated_idea = {
                'title': f"{idea.get('title', 'Project')} - Escalation L{level_idx + 1} (v{variation + 1})",
                'description': idea.get('description', ''),
                'code': idea.get('code', ''),
                'language': idea.get('language', 'Python'),
                'is_escalated_retry': True,
                'escalation_level': level,
                'escalation_index': level_idx + 1,
                'variation': variation + 1,
                'original_project': project_name,
                'base_project_name': project_name,  # Track base name for throttling
                'error_context': error_text,
                'error_type': error_type,
                'learning_reuse_applicable': len(similar_fixes) > 0,
                'similar_fixes_count': len(similar_fixes),
                'learning_db_reuse_rate': reuse_rate,
                'priority': 5 + level_idx  # Lower priority for aggressive levels
            }
            
            # Add specific instructions for each level
            instructions = {
                'Conservative': 'Focus on fixing specific identified errors while maintaining code quality.',
                'Moderate': 'Be more aggressive with refactoring to fix root causes. Consider alternative approaches.',
                'Aggressive': 'Completely rewrite if necessary. Try different design patterns and libraries.',
                'Nuclear': 'Use the most powerful approach available. Break compatibility if needed to make it work.'
            }
            
            escalated_idea['escalation_instruction'] = instructions[level]
            
            # Add learning database suggestions if we have similar fixes
            if similar_fixes:
                escalated_idea['learned_fixes'] = similar_fixes[:3]  # Top 3 similar fixes
                escalated_idea['description'] += f"\n\n[Learning DB: {len(similar_fixes)} similar fixes found with {reuse_rate:.1f}% reuse rate]"
            
            escalated_ideas.append(escalated_idea)
    
    return escalated_ideas


if __name__ == "__main__":
    # Example usage
    db = LearningFixDatabase()
    print("📚 Learning Fix Database")
    print(f"Total fixes learned: {db.db['metadata']['total_fixes']}")
    stats = db.get_stats()
    print(f"Reuse rate: {stats['reuse_rate']:.1f}%")
    print(f"Error types tracked: {stats['error_types_tracked']}")
