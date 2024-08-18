"""Utility helper functions"""

import re
from typing import Dict, List, Literal, Tuple


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


def pick(obj: Dict, key_map: Dict[str, str | bool] = None) -> Dict:
    _obj = {}
    keys = [] if not key_map else key_map.keys()

    for key, value in obj.items():
        if key_map:
            if key not in keys or not key_map[key]: continue
        
            key = key_map[key]

        _obj[key] = value

    return _obj
        