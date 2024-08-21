import re
from utils.helpers import count_required_args
from typing import Any, Callable, Dict, List

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


def assign(
    value: Any,
    obj: List | Dict,
    path: str | List[str],
    delimiter: str = '.',
    merge: bool = False
):
    if type(path) == str:
        path = split(path, delimiter)
        
    _obj = obj
    size = len(path)
    if not size: return _obj
    
    for i, key in enumerate(path):
        if i == size - 1:
            if merge and has_key(_obj, key) and type(_obj[key] == type(value)):
                if type(value) in [str, int, list]:
                    _obj[key] += value
                elif type(value) == dir:
                    _obj[key] |= value
            else: _obj[key] = value
        else:
            _obj = _obj[key]

    return obj


def resolve(
    path: str|List[str],
    obj: List | Dict,
    vars: Dict = {},
    delimiter: str = '.',
    resolve_key: Callable = lambda k:k,
    strict: bool = False
) -> List:
    if type(path) == str:
        path = split(path, delimiter)
    
    if not len(path): return path

    resolved_path = []
    value = obj

    for i in range(len(path)):
        args_count = count_required_args(resolve_key)
        args = [path[i], value, vars, obj]

        if args_count > 4: args += [obj] * (args_count - 4)

        key = resolve_key(*args[0:args_count])
            
        if not ((type(value) is list or type(value) is dict) and has_key(value, key)):
            if strict: raise KeyError(f'Unable to resolve key "{key}"')
            else:
                resolved_path.append(key)
                continue

        value = value[key]
        resolved_path.append(key)

    return resolved_path


def has_key(obj, key) -> bool:
    if type(obj) in [list, str]:
        return key in dict(enumerate(obj))
    elif type(obj) is dict:
        return key in obj
    else:
        return hasattr(obj, key)