---
name: python-code-review
description: Reviews Python code for PEP8 compliance, type hints, modern best practices (Python 3.9+), and code quality. Detects anti-patterns, validates documentation, and provides severity-based recommendations. Integrates with modern tooling (ruff, mypy, uv).
---

# Python Code Review Skill

A specialized skill for reviewing Python code with focus on PEP8 compliance, type hints, modern best practices, and code quality.

## Overview

This skill enables Claude to autonomously review Python code for compliance with modern Python standards, including PEP8 style guidelines, type hint coverage, proper structure, and common anti-patterns. It promotes clean, maintainable, and type-safe Python code.

## Capabilities

When activated, this skill provides:

1. **PEP8 Compliance Review**
   - Check naming conventions (snake_case, PascalCase)
   - Verify line length (88 characters)
   - Review whitespace and indentation
   - Check import ordering and grouping
   - Validate docstring presence and format

2. **Type Hints Validation**
   - Ensure all functions have type hints
   - Check for proper return type annotations
   - Validate use of modern type syntax (list[], dict[] over List[], Dict[])
   - Verify Optional[] vs None union types
   - Check for Any types (discourage overuse)

3. **Code Structure & Organization**
   - Review module structure and imports
   - Check for proper `__init__.py` usage
   - Validate entry points (`__main__.py`)
   - Review function/class organization
   - Assess module coupling and cohesion

4. **Best Practices Enforcement**
   - Check for use of context managers (with statements)
   - Validate exception handling
   - Review string formatting (f-strings preferred)
   - Check for proper constant definitions
   - Assess use of comprehensions vs loops

5. **Common Anti-Patterns Detection**
   - Mutable default arguments
   - Bare except clauses
   - Using `global` keyword unnecessarily
   - Poor variable naming
   - Overly complex functions (high cyclomatic complexity)

6. **Documentation Quality**
   - Check for docstrings on public functions/classes
   - Validate docstring format (Google/NumPy style)
   - Review parameter documentation
   - Check for return value documentation
   - Assess example usage in docstrings

## Usage

This skill activates automatically when:
- User requests: "Review this Python code"
- User asks: "Check PEP8 compliance"
- User mentions: "Validate type hints"
- User wants: "Improve this Python code"
- Code review is requested for .py files
- User asks: "Is this code following best practices?"

## Review Approach

### 1. Initial Assessment
- Identify Python version being used
- Understand the code's purpose
- Determine if it's application code or library code
- Check project structure context

### 2. PEP8 Compliance Check

**Naming Conventions:**
- ✅ Functions/variables: `snake_case`
- ✅ Classes: `PascalCase`
- ✅ Constants: `UPPER_SNAKE_CASE`
- ✅ Private members: `_leading_underscore`
- ✅ Module names: `lowercase` or `snake_case`

**Code Layout:**
- ✅ Line length: 88 characters (Black standard)
- ✅ Indentation: 4 spaces
- ✅ Blank lines: 2 before top-level definitions, 1 between methods
- ✅ Import order: stdlib → third-party → local
- ✅ One import per line (except from imports)

### 3. Type Hints Review

**Check for:**
```python
# ❌ Missing type hints
def process(data):
    return data.upper()

# ✅ Proper type hints
def process(data: str) -> str:
    return data.upper()

# ❌ Old-style typing (Python <3.9)
from typing import List, Dict
def get_items() -> List[Dict[str, int]]:
    pass

# ✅ Modern type syntax (Python 3.9+)
def get_items() -> list[dict[str, int]]:
    pass

# ❌ Overuse of Any
from typing import Any
def process(data: Any) -> Any:
    pass

# ✅ Specific types
def process(data: str | int) -> str:
    return str(data)
```

### 4. Common Issues Detection

**Mutable Default Arguments:**
```python
# ❌ Dangerous
def append_to(element: str, target: list[str] = []) -> list[str]:
    target.append(element)
    return target

# ✅ Safe
def append_to(element: str, target: list[str] | None = None) -> list[str]:
    if target is None:
        target = []
    target.append(element)
    return target
```

**Exception Handling:**
```python
# ❌ Bare except
try:
    risky_operation()
except:
    pass

# ✅ Specific exception
try:
    risky_operation()
except ValueError as e:
    logger.error(f"Invalid value: {e}")
    raise
```

**String Formatting:**
```python
# ❌ Old style
name = "World"
print("Hello %s" % name)
print("Hello {}".format(name))

# ✅ Modern f-strings
print(f"Hello {name}")
```

**Context Managers:**
```python
# ❌ Manual resource management
file = open("data.txt")
data = file.read()
file.close()

# ✅ Context manager
with open("data.txt") as file:
    data = file.read()
```

### 5. Code Quality Assessment

**Function Complexity:**
- Functions should do one thing well
- Aim for <20 lines per function
- Cyclomatic complexity should be low (<10)
- Deep nesting (>3 levels) indicates need for refactoring

**Example - Complex to Simple:**
```python
# ❌ Too complex
def process_user(user):
    if user:
        if user.active:
            if user.email:
                if "@" in user.email:
                    return user.email.lower()
    return None

# ✅ Simplified
def process_user(user: User | None) -> str | None:
    if not user or not user.active or not user.email:
        return None
    
    if "@" not in user.email:
        return None
        
    return user.email.lower()
```

## Output Format

Provide review results in this structured format:

```markdown
## Python Code Review Results

### Summary
[Brief overview of the code quality and main findings]

### PEP8 Compliance: [PASS/FAIL/PARTIAL]
**Issues Found:**
- Line 15: Line too long (102 characters, limit 88)
- Line 23: Missing blank line after function definition
- Line 45: Import should be at top of file

### Type Hints Coverage: [X%]
**Missing Type Hints:**
- Line 10: Function `process_data` missing return type
- Line 18: Parameter `config` missing type annotation
- Line 25: Using deprecated `List` instead of `list`

**Recommendations:**
```python
# Current
def process_data(items, limit=10):
    return items[:limit]

# Improved
def process_data(items: list[str], limit: int = 10) -> list[str]:
    return items[:limit]
```

### Code Quality Issues

#### Critical 🔴
- **Line 34**: Mutable default argument in `add_item(item, items=[])`
- **Line 56**: Bare except clause catching all exceptions

#### Important 🟡
- **Line 12**: Function complexity too high (15 branches)
- **Line 78**: Using `global` keyword - consider refactoring
- **Line 91**: Variable name `x` is not descriptive

#### Minor 🔵
- **Line 23**: Could use f-string instead of .format()
- **Line 45**: List comprehension would be more Pythonic

### Best Practices Violations

1. **Line 15-18: Manual file handling**
   - **Current:**
   ```python
   f = open("data.txt")
   data = f.read()
   f.close()
   ```
   - **Improved:**
   ```python
   with open("data.txt") as f:
       data = f.read()
   ```

2. **Line 34: Mutable default argument**
   - **Impact**: Can cause bugs when function is called multiple times
   - **Fix**: Use None as default, create new list inside function

### Positive Aspects ✅
- Consistent naming conventions throughout
- Good use of type hints in 80% of functions
- Proper docstrings on all public methods
- Clean import organization

### Documentation Review
- ✅ All public functions have docstrings
- ✅ Docstrings follow Google style format
- ⚠️ Some docstrings missing return value description
- ⚠️ No examples in docstrings (consider adding for complex functions)

### Modernization Suggestions
- Update to Python 3.10+ syntax (use `|` for unions instead of `Union`)
- Consider using `match/case` statement (Python 3.10+) for complex conditionals
- Replace `Dict`, `List` with `dict`, `list` (Python 3.9+)

### Next Steps
1. Fix critical issues (mutable defaults, bare excepts)
2. Add missing type hints
3. Refactor complex functions (>15 lines)
4. Run automated tools:
   ```bash
   uv run ruff check .          # Linting
   uv run mypy .                # Type checking
   uv run ruff format .         # Auto-formatting
   ```

### Recommended Tools
- **ruff**: Fast linting and formatting (replaces black, flake8, isort)
- **mypy**: Static type checking
- **pytest**: Testing framework
- **coverage**: Code coverage analysis

### Overall Assessment: [GOOD/NEEDS IMPROVEMENT/EXCELLENT]
[Brief summary and priority recommendations]
```

## Review Standards

### PEP8 Checklist

**Naming:**
- [ ] Functions and variables use snake_case
- [ ] Classes use PascalCase
- [ ] Constants use UPPER_SNAKE_CASE
- [ ] Private members start with underscore

**Formatting:**
- [ ] Line length ≤ 88 characters
- [ ] 4 spaces for indentation (no tabs)
- [ ] 2 blank lines before class/function definitions
- [ ] 1 blank line between methods

**Imports:**
- [ ] Grouped: stdlib → third-party → local
- [ ] Alphabetically sorted within groups
- [ ] No wildcard imports (`from module import *`)
- [ ] Unused imports removed

### Type Hints Standards

**Required:**
```python
# All function parameters
def func(name: str, age: int) -> None:
    pass

# Return types (even None)
def get_data() -> dict[str, Any]:
    pass

# Class attributes
class User:
    name: str
    age: int
    
    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age
```

**Modern Syntax (Python 3.9+):**
- Use `list[]` not `List[]`
- Use `dict[]` not `Dict[]`
- Use `tuple[]` not `Tuple[]`
- Use `set[]` not `Set[]`
- Use `|` not `Union[]` (Python 3.10+)

### Documentation Standards

**Google Style Docstrings:**
```python
def function_name(param1: str, param2: int) -> bool:
    """Brief description of function.
    
    Longer description explaining what the function does,
    its behavior, and any important details.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When param2 is negative
        
    Example:
        >>> function_name("test", 5)
        True
    """
    pass
```

## Best Practices to Promote

1. **Use type hints everywhere** - Improves IDE support and catches bugs early
2. **Prefer f-strings** - More readable than format() or %
3. **Use context managers** - For file handling, locks, connections
4. **Write small functions** - Each function should do one thing well
5. **Use comprehensions** - More Pythonic than loops for simple transformations
6. **Avoid global state** - Pass dependencies explicitly
7. **Use dataclasses** - For data containers (Python 3.7+)
8. **Use pathlib** - Instead of os.path for file operations
9. **Use enums** - For fixed sets of constants
10. **Write docstrings** - For all public APIs

## Common Refactoring Patterns

### Replace Loop with Comprehension
```python
# ❌ Before
result = []
for item in items:
    if item.active:
        result.append(item.name)

# ✅ After
result = [item.name for item in items if item.active]
```

### Use Dataclass
```python
# ❌ Before
class User:
    def __init__(self, name, email, age):
        self.name = name
        self.email = email
        self.age = age

# ✅ After
from dataclasses import dataclass

@dataclass
class User:
    name: str
    email: str
    age: int
```

### Use Pathlib
```python
# ❌ Before
import os
path = os.path.join("data", "file.txt")
if os.path.exists(path):
    with open(path) as f:
        data = f.read()

# ✅ After
from pathlib import Path
path = Path("data") / "file.txt"
if path.exists():
    data = path.read_text()
```

## Integration

This skill works seamlessly with:
- Code review workflows
- Pull request reviews
- Refactoring tasks
- Code quality improvement projects
- Pre-commit validation
- Migration to modern Python versions
- Type hint adoption projects
