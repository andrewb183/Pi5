#!/usr/bin/env python3
"""
Hard Fix Database - Persistent code block fix system

When a project fails 4 times (including smart retry):
1. Extract the specific error and problematic code block
2. Keep retrying JUST that code block with variations
3. Once it works, save to hard_fixes_database.json
4. Future projects can use proven fixes for similar issues

This creates a growing library of working solutions.
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import hashlib


class HardFixDatabase:
    def __init__(self):
        self.db_path = Path('implementation_outputs/hard_fixes_database.json')
        self.active_fixes_path = Path('implementation_outputs/active_fix_attempts.json')
        self.db = self.load_database()
        
    def load_database(self) -> Dict:
        """Load the hard fixes database."""
        if not self.db_path.exists():
            return {
                'fixes': {},
                'metadata': {
                    'total_fixes': 0,
                    'last_updated': datetime.now().isoformat()
                }
            }
        with open(self.db_path) as f:
            return json.load(f)
    
    def save_database(self):
        """Save the hard fixes database."""
        self.db['metadata']['last_updated'] = datetime.now().isoformat()
        self.db['metadata']['total_fixes'] = len(self.db['fixes'])
        with open(self.db_path, 'w') as f:
            json.dump(self.db, f, indent=2)
    
    def extract_error_and_code_block(self, project_dir: Path, error_log: List[Dict]) -> Optional[Dict]:
        """Extract the specific error and problematic code block."""
        if not error_log:
            return None
        
        # Get the most recent error
        latest_error = error_log[-1]
        error_message = latest_error.get('error_message', '')
        error_type = latest_error.get('error_type', '')
        
        # Try to find the main code file
        code_file = None
        for ext in ['.py', '.js', '.java', '.cpp', '.cs', '.go', '.rs']:
            potential = project_dir / f'main{ext}'
            if potential.exists():
                code_file = potential
                break
        
        if not code_file or not code_file.exists():
            return None
        
        code_content = code_file.read_text()
        
        # Extract line number from error if available
        line_number = None
        line_match = re.search(r'line (\d+)', error_message, re.IGNORECASE)
        if line_match:
            line_number = int(line_match.group(1))
        
        # Extract problematic code block
        code_lines = code_content.split('\n')
        
        if line_number:
            # Get context around the error (10 lines before and after)
            start = max(0, line_number - 11)  # -1 for 0-indexing, -10 for context
            end = min(len(code_lines), line_number + 10)
            problem_block = '\n'.join(code_lines[start:end])
            block_start_line = start + 1
        else:
            # If no line number, try to find the problematic section by error type
            if 'syntax' in error_type.lower() or 'SyntaxError' in error_message:
                # Find incomplete structures
                problem_block = self._find_syntax_issue(code_content)
                block_start_line = 1
            elif 'import' in error_message.lower() or 'ModuleNotFoundError' in error_message:
                # Get import section
                import_lines = [i for i, line in enumerate(code_lines) if 'import' in line]
                if import_lines:
                    problem_block = '\n'.join(code_lines[:max(import_lines) + 5])
                    block_start_line = 1
                else:
                    problem_block = '\n'.join(code_lines[:20])
                    block_start_line = 1
            else:
                # Take first 30 lines as default
                problem_block = '\n'.join(code_lines[:30])
                block_start_line = 1
        
        # Create error signature for matching similar issues
        error_signature = self._create_error_signature(error_type, error_message)
        
        return {
            'error_type': error_type,
            'error_message': error_message,
            'error_signature': error_signature,
            'code_block': problem_block,
            'block_start_line': block_start_line,
            'full_file_path': str(code_file),
            'language': code_file.suffix[1:],  # Remove the dot
            'extracted_at': datetime.now().isoformat()
        }
    
    def _create_error_signature(self, error_type: str, error_message: str) -> str:
        """Create a signature for matching similar errors."""
        # Normalize the error message
        normalized = error_message.lower()
        # Remove line numbers and file paths
        normalized = re.sub(r'line \d+', 'line X', normalized)
        normalized = re.sub(r'/[^\s]+', '/path', normalized)
        normalized = re.sub(r'["\'].*?["\']', 'STRING', normalized)
        
        # Create hash
        signature = f"{error_type}:{normalized}"
        return hashlib.md5(signature.encode()).hexdigest()[:16]
    
    def _find_syntax_issue(self, code: str) -> str:
        """Try to identify the section with syntax issues."""
        lines = code.split('\n')
        
        # Look for common syntax problems
        for i, line in enumerate(lines):
            # Unclosed brackets/parens
            if line.count('(') != line.count(')') or \
               line.count('[') != line.count(']') or \
               line.count('{') != line.count('}'):
                start = max(0, i - 5)
                end = min(len(lines), i + 15)
                return '\n'.join(lines[start:end])
            
            # TODO or placeholder comments that might break code
            if 'TODO' in line or 'FIXME' in line or '# ...' in line:
                start = max(0, i - 5)
                end = min(len(lines), i + 15)
                return '\n'.join(lines[start:end])
        
        # Default: return first 30 lines
        return '\n'.join(lines[:30])
    
    def create_fix_attempt(self, project_name: str, error_data: Dict, attempt_number: int) -> Dict:
        """Create a new fix attempt with specific instructions."""
        language = error_data['language']
        error_type = error_data['error_type']
        error_message = error_data['error_message']
        problem_block = error_data['code_block']
        
        # Check if we have similar fixes in the database
        similar_fix = self.find_similar_fix(error_data['error_signature'], language)
        
        # Generate fix instructions based on attempt number and similar fixes
        if similar_fix:
            fix_instructions = f"""PROVEN FIX FOUND - Use this working solution:

{similar_fix['fix_description']}

Working code example:
```{language}
{similar_fix['working_code'][:500]}
```

Success rate: {similar_fix['success_count']}/{similar_fix['total_attempts']}"""
        else:
            # Generate targeted fix instructions
            fix_instructions = self._generate_targeted_fix(
                error_type, error_message, problem_block, language, attempt_number
            )
        
        return {
            'project_name': project_name,
            'attempt_number': attempt_number,
            'error_data': error_data,
            'fix_instructions': fix_instructions,
            'has_similar_fix': similar_fix is not None,
            'created_at': datetime.now().isoformat()
        }
    
    def _generate_targeted_fix(self, error_type: str, error_message: str, 
                               code_block: str, language: str, attempt: int) -> str:
        """Generate increasingly aggressive fix instructions."""
        base_instructions = f"""TARGET: Fix this specific {language} code block

ERROR: {error_message}
TYPE: {error_type}

PROBLEMATIC CODE:
```{language}
{code_block[:300]}
```

"""
        
        # Escalating fix strategies based on attempt number
        strategies = [
            # Attempt 1: Gentle fix
            """FIX STRATEGY (Attempt 1 - Conservative):
1. Fix obvious syntax errors in the block above
2. Ensure proper indentation and brackets
3. Complete any incomplete statements
4. Keep the logic the same, just fix syntax""",
            
            # Attempt 2: More aggressive
            """FIX STRATEGY (Attempt 2 - Moderate):
1. Rewrite the problematic section with correct syntax
2. Remove any TODO/placeholder comments
3. Use simpler expressions
4. Add proper error handling""",
            
            # Attempt 3: Significant changes
            """FIX STRATEGY (Attempt 3 - Aggressive):
1. Completely rewrite this section
2. Use the most basic approach possible
3. Remove unnecessary complexity
4. Use standard library functions only
5. Add defensive checks everywhere""",
            
            # Attempt 4+: Nuclear option
            """FIX STRATEGY (Attempt 4+ - Complete Redesign):
1. START FROM SCRATCH for this section
2. Use the absolute simplest working code
3. No clever tricks, just basic patterns
4. Copy from standard library examples
5. Test each line mentally before writing"""
        ]
        
        strategy_index = min(attempt - 1, len(strategies) - 1)
        return base_instructions + strategies[strategy_index]
    
    def find_similar_fix(self, error_signature: str, language: str) -> Optional[Dict]:
        """Find a proven fix for a similar error."""
        fixes = self.db.get('fixes', {})
        
        for fix_id, fix_data in fixes.items():
            if (fix_data.get('error_signature') == error_signature and 
                fix_data.get('language') == language and
                fix_data.get('verified', False)):
                return fix_data
        
        return None
    
    def save_working_fix(self, project_name: str, error_data: Dict, 
                        working_code: str, fix_description: str):
        """Save a proven working fix to the database."""
        fix_id = f"{error_data['error_signature']}_{error_data['language']}"
        
        if fix_id in self.db['fixes']:
            # Update existing fix
            self.db['fixes'][fix_id]['success_count'] += 1
            self.db['fixes'][fix_id]['total_attempts'] += 1
            self.db['fixes'][fix_id]['last_used'] = datetime.now().isoformat()
            self.db['fixes'][fix_id]['projects'].append(project_name)
        else:
            # Create new fix entry
            self.db['fixes'][fix_id] = {
                'error_signature': error_data['error_signature'],
                'error_type': error_data['error_type'],
                'error_message_pattern': error_data['error_message'][:200],
                'language': error_data['language'],
                'working_code': working_code[:1000],  # Store first 1000 chars
                'fix_description': fix_description,
                'success_count': 1,
                'total_attempts': 1,
                'verified': True,
                'created_at': datetime.now().isoformat(),
                'last_used': datetime.now().isoformat(),
                'projects': [project_name]
            }
        
        self.save_database()
        print(f"  💾 Saved working fix to database: {fix_id}")
        print(f"     Success rate: {self.db['fixes'][fix_id]['success_count']}/{self.db['fixes'][fix_id]['total_attempts']}")


def main():
    """Test the hard fix database."""
    db = HardFixDatabase()
    
    print("🔧 Hard Fix Database System\n")
    print("=" * 70)
    
    # Show database stats
    total_fixes = len(db.db.get('fixes', {}))
    print(f"\nDatabase Statistics:")
    print(f"  Total proven fixes: {total_fixes}")
    
    if total_fixes > 0:
        print(f"\nProven fixes by type:")
        fixes = db.db['fixes']
        by_type = {}
        for fix_data in fixes.values():
            error_type = fix_data['error_type']
            by_type[error_type] = by_type.get(error_type, 0) + 1
        
        for error_type, count in sorted(by_type.items()):
            print(f"    {error_type}: {count} fixes")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
