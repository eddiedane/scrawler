import re
from typing import Dict, List, Literal, Tuple
from colorama import Fore


ParseValueData = Dict[Literal['prop', 'ctx', 'selector', 'max', 'utils', 'parsed_utils'], str | List | None]


def parse_value(string: str) -> ParseValueData:
    value_re = r'(?P<prop>[^|}@]+)(?:@(?:<(?P<ctx>page|parent)(?:\.(?P<max>all|one)?)>)?(?P<selector>[^|<]+))?(?:\s*\|\s*(?P<utils>\w+(?:\s+[^\s]+)*))*\s*'
    match = re.fullmatch(value_re, string)

    if not match:
        return {'prop': None, 'ctx': None, 'selector': None, 'utils': None, 'parsed_utils': []}
    
    data: ParseValueData = match.groupdict()
    data['prop'] = (data['prop'] or '').strip()
    data['selector'] = (data['selector'] or '').strip()
    data['utils'] = (data['utils'] or '').strip()
    data['ctx'] = data['ctx'] or 'parent'

    if not data['utils']:
        data['parsed_utils'] = []

        return data
    
    util_notns = re.split(r'\s*\|\s*', data['utils'])
    parsed_utils = []

    for util_notn in util_notns:
        util_parts = re.split(r'\s+', util_notn.strip())
        parsed_utils.append((util_parts[0], util_parts[1:]))

    data['parsed_utils'] = parsed_utils

    return data


def parse_getters(string: str) -> List[Tuple[str, str, str]]:
    return set(re.findall(r'(\$(var|attr)\{\s*([^|}]+(?:\s*\|\s*\w+(?:\s+[^\s{}]+)*)*\s*)\})', string))


def find_item_key(key, match, value, vars, _):
    sub_key = match.group(1)
    operator = match.group(2)
    var_sign = match.group(3)
    operand = match.group(4)

    if var_sign:
        operand = vars[operand]

    if type(value) is dict: items = value.items()
    elif type(value) is list: items = enumerate(value)
    else: raise TypeError(f'Invalid operation type at "{key}"')

    for k, v in items:
        found = False

        match operator:
            case '=': found = v[sub_key] == operand
            case '!=': found = v[sub_key] != operand
            case '>=': found = v[sub_key] >= operand
            case '<=': found = v[sub_key] <= operand
            case '>': found = v[sub_key] > operand
            case '<': found = v[sub_key] < operand
            case _: raise ValueError(f'Invalid operator "{operator}"')
        
        if found: return k
    else:
        raise ValueError(Fore.RED + 'No match found at ' + Fore.CYAN + f'"{key}"' + Fore.RED + ' when operand is ' + Fore.BLUE + f'"{operand}"' + Fore.RESET)
    