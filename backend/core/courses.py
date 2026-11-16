"""Canonical course codes shared by registration, profile edit, search and requests."""

import re

# Letters, optional spaces/hyphens, then digits (and an optional trailing letter):
# "csc510", "CSC-510" and " CSC  510 " all become "CSC 510".
_CODE = re.compile(r"([A-Z]+)[ -]*([0-9][A-Z0-9]*)")


def normalize_code(value):
    """Return the canonical form of a course code; anything unrecognised is just
    trimmed, upper-cased and has its whitespace collapsed."""
    text = re.sub(r"\s+", " ", value).strip().upper()
    match = _CODE.fullmatch(text)
    return f"{match.group(1)} {match.group(2)}" if match else text
