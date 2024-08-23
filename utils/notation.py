import re
from typing import Dict, List, Literal, Tuple
from colorama import Fore


ParseValueData = Dict[Literal['prop', 'child_node', 'ctx', 'selector', 'max', 'utils', 'parsed_utils', 'var'], int | str | List | None]
KeyMatchData = Dict[Literal['is_left_var', 'left_operand', 'operator', 'is_right_var', 'right_operand'], str]


def parse_value(string: str) -> ParseValueData:
    value_re = r'(?:(?P<prop>\w+)(?::child\((?P<child_node>\d+)\))?)\s*(?:@\s*(?:<(?P<ctx>page|parent)(?:\.(?P<max>all|first))?>)?(?P<selector>[^|<]+))?(?:\s*\|\s*(?P<utils>\w+(?:\s+[^>]+)*))*\s*(?:>>\s*(?P<var>\w+))?'
    match = re.fullmatch(value_re, string)

    if not match:
        return {'prop': None, 'ctx': None, 'selector': None, 'utils': None, 'parsed_utils': []}
    
    data: ParseValueData = match.groupdict()
    data['prop'] = (data['prop'] or '').strip()
    data['child_node'] = int(data['child_node']) if data['child_node'] else None
    data['selector'] = (data['selector'] or '').strip()
    data['utils'] = (data['utils'] or '').strip()
    data['ctx'] = data['ctx'] or 'parent'
    data['max'] = data['max'] or 'one'

    if not data['utils']:
        data['parsed_utils'] = []

        return data
    
    utils = re.split(r'\s*\|\s*', data['utils'])
    parsed_utils = []

    for util in utils:
        util_parts = re.split(r'\s+', util.strip())
        parsed_utils.append((util_parts[0], util_parts[1:]))

    data['parsed_utils'] = parsed_utils

    return data


def parse_getters(string: str) -> List[Tuple[str, str, str]]:
    return set(re.findall(r'(\$(var|attr)\{\s*([^|}]+(?:\s*\|\s*\w+(?:\s+[^\s{}]+)*)*\s*)\})', string))


def find_item_key(key, value, vars):
    key_re = r'\$key\{\s*(?P<is_left_var>\$)?(?P<left_operand>\w+)\s*(?P<operator>=|!=|>=|<=|>|<)\s*(?P<is_right_var>\$)?(?P<right_operand>\w+)\s*\}'
    match = re.search(key_re, key)

    if not match: return key

    match_data: KeyMatchData = match.groupdict()
    operator = match_data['operator']
    left_operand = vars[match_data['left_operand']] if match_data['is_left_var'] else match_data['left_operand']
    right_operand = vars[match_data['right_operand']] if match_data['is_right_var'] else match_data['right_operand']

    if type(value) is dict: items = value.items()
    elif type(value) is list: items = enumerate(value)
    else: raise TypeError(Fore.RED + f'Invalid operation type (dict and list only) at ' + Fore.CYAN + key + Fore.RESET)

    for k, v in items:
        found = False

        match operator:
            case '=': found = v[left_operand] == right_operand
            case '!=': found = v[left_operand] != right_operand
            case '>=': found = v[left_operand] >= right_operand
            case '<=': found = v[left_operand] <= right_operand
            case '>': found = v[left_operand] > right_operand
            case '<': found = v[left_operand] < right_operand
            case _: raise ValueError(Fore.RED + 'Invalid operator ' + Fore.CYAN + operator + Fore.RED + ' at ' + Fore.CYAN + key + Fore.RESET)
        
        if found: return k
    else:
        raise ValueError(Fore.RED + 'No match found at ' + Fore.CYAN + key + Fore.RED + ' with comparsion of ' + Fore.BLUE + f'{left_operand}{operator}{right_operand}' + Fore.RESET)
    