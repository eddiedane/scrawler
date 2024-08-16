"""Utility helper functions"""

import re
from typing import Literal


def is_file_type(typ: Literal['yaml', 'json'], filename: str) -> bool:
    """Check for limited file types (json and yaml), appropriate for configs"""

    if re.search(r'[^.]*\.(yaml|yml)$', filename) and typ == 'yaml':
        return True
    elif re.search(r'[^.]*\.json$', filename) and typ == 'json':
        return True
    
    return False