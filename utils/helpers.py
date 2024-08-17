"""Utility helper functions"""

import re
from typing import List, Literal


def flatten_list(l: List) -> List:
    items = []

    for item in l:
        if type(item) is list:
            rst = flatten_list(item)
            items = items + rst
        else:
            items.append(item)

    return items


def is_file_type(typ: Literal['yaml', 'json'], filename: str) -> bool:
    """Check for limited file types (json and yaml), appropriate for configs"""

    if re.search(r'[^.]*\.(yaml|yml)$', filename) and typ == 'yaml':
        return True
    elif re.search(r'[^.]*\.json$', filename) and typ == 'json':
        return True
    
    return False