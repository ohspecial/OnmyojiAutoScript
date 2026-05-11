"""CI grep rule: assert rewritten files do NOT import banned legacy symbols.

Validates: Requirements 5.7, 6.4, 7.5

The rewritten agent.py, focus.py, and debugger.py MUST NOT import:
- CLASSINDEX
- MIN_BUFF, MAX_BUFF, MIN_N, MAX_N, MIN_G, MAX_G, MIN_R, MAX_R,
  MIN_SR, MAX_SR, MIN_SSR, MAX_SSR, MIN_SP, MAX_SP
- BUFF_001 through BUFF_007
- R_007, R_008 (as constants from CLASSINDEX)

They MAY reference _registry (the module-level Registry instance) and use
tier/tag-based dispatch instead.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Files that must be free of banned imports
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_REWRITTEN_FILES = [
    _PROJECT_ROOT / "tasks" / "Hyakkiyakou" / "agent" / "agent.py",
    _PROJECT_ROOT / "tasks" / "Hyakkiyakou" / "agent" / "focus.py",
    _PROJECT_ROOT / "module" / "hyakkiyakou" / "debugger.py",
]

# Patterns that indicate banned legacy imports
_BANNED_PATTERNS = [
    # Direct import of CLASSINDEX
    r"\bfrom\s+oashya\.labels\s+import\b.*\bCLASSINDEX\b",
    r"\bimport\s+.*\bCLASSINDEX\b",
    # Usage of CI.MIN_X / CI.MAX_X
    r"\bCI\.MIN_",
    r"\bCI\.MAX_",
    r"\bCLASSINDEX\.MIN_",
    r"\bCLASSINDEX\.MAX_",
    # Usage of CI.BUFF_00X
    r"\bCI\.BUFF_\d+",
    r"\bCLASSINDEX\.BUFF_\d+",
    # Usage of CI.R_007 / CI.R_008
    r"\bCI\.R_00[78]\b",
    r"\bCLASSINDEX\.R_00[78]\b",
    # Direct import of MIN_*/MAX_*/BUFF_*/R_00X from oashya.labels
    r"\bfrom\s+oashya\.labels\s+import\b.*\b(MIN_|MAX_|BUFF_\d|R_00[78])",
]


@pytest.mark.parametrize("filepath", _REWRITTEN_FILES, ids=lambda p: p.name)
def test_no_banned_imports(filepath: Path):
    """Assert that rewritten files do not contain banned legacy imports."""
    assert filepath.exists(), f"File not found: {filepath}"

    content = filepath.read_text(encoding="utf-8")
    violations = []

    for pattern in _BANNED_PATTERNS:
        matches = re.findall(pattern, content)
        if matches:
            violations.append(f"  Pattern {pattern!r} matched: {matches}")

    assert not violations, (
        f"Banned legacy imports found in {filepath.name}:\n"
        + "\n".join(violations)
    )


@pytest.mark.parametrize("filepath", _REWRITTEN_FILES, ids=lambda p: p.name)
def test_no_oashya_labels_import(filepath: Path):
    """Assert that rewritten files do not import from oashya.labels at all."""
    assert filepath.exists(), f"File not found: {filepath}"

    content = filepath.read_text(encoding="utf-8")

    # Check for any import from oashya.labels
    oashya_import = re.findall(
        r"^\s*(?:from\s+oashya\.labels\s+import|import\s+oashya\.labels)",
        content,
        re.MULTILINE,
    )

    assert not oashya_import, (
        f"Found oashya.labels import in {filepath.name}:\n"
        + "\n".join(f"  {line}" for line in oashya_import)
    )
