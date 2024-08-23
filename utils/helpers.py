"""Utility helper functions"""

import re, inspect
from typing import Any, Dict, List, Literal, Set


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
    

def count_required_args(func):
    # Get the signature of the function
    sig = inspect.signature(func)
    # Count the number of required arguments
    required_args = sum(
        1 for param in sig.parameters.values()
        if param.default == inspect.Parameter.empty and
           param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.KEYWORD_ONLY)
    )
    
    return required_args


def is_none_keys(obj: Dict, *keys) -> bool:
    for key in keys:
        if key in obj and obj[key] is not None: return False
    
    return True