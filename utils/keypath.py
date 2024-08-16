import re
from typing import Any, Dict, List

def split(path: str, delimiter: str = '.') -> List[str]:
    sanitized_path = re.sub(r'\]+$', '', path)
    sanitized_path = re.sub(r'[\[\]]+', delimiter, path)
    sanitized_path = re.sub(r'\.{2,}', delimiter, path)
    
    return sanitized_path.split(delimiter)


def get(
    path: str|List[str],
    obj: List | Dict,
    default: Any = None,
    delimiter: str = '.',
) -> Any:
    if type(path) == str:
        path = split(path, delimiter)

    if not len(path): return default

    value = obj

    for key in path:
        if not (type(value) in [dict, list, str] and has_key(value, key)):
            return default
        
        value = value[key]

    return value


def has_key(obj, key) -> bool:
    if type(obj) in [list, str]:
        return key in dict(enumerate(obj))
    elif type(obj) is dict:
        return key in obj
    else:
        return hasattr(obj, key)