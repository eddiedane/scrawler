"""Utility helper functions"""

import re
from typing import Any, Dict, Literal, Set


def is_file_type(typ: Literal['yaml', 'json'], filename: str) -> bool:
    """Check for limited file types (json and yaml), appropriate for configs"""

    if re.search(r'[^.]*\.(yaml|yml)$', filename) and typ == 'yaml':
        return True
    elif re.search(r'[^.]*\.json$', filename) and typ == 'json':
        return True
    
    return False


def pick(obj: Dict, key_map: Set | Dict[str, str] = {}) -> Dict:
    _obj = {}
    
    if type(key_map) is set:
        _key_map = {}

        for key in key_map: _key_map[key] = key

        key_map = _key_map


    keys = [] if not key_map else key_map.keys()

    for key, value in obj.items():
        if key not in keys: continue
        
        key = key_map[key]
        _obj[key] = value

    return _obj
        

def is_numeric(val: Any) -> bool:
    try:
        float(val)
        return True
    except:
        return False