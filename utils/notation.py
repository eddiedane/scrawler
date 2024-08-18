from typing import Dict, List, Tuple
from colorama import Fore
from pprint import pprint


def parse_interaction(notation: str) -> Dict[str, str|List]:
    interaction = {}
    vals = notation.split('@')
    interaction['node'] = vals[0]

    if interaction['node'][0] == '?':
        interaction['optional'] = True
        interaction['node'] = interaction['node'][1:]

    interaction['actions'] = [parse_action(act_notation) for act_notation in vals[1:]]
    
    return interaction


def parse_action(notation: str) -> Dict[str, str|int]:
    vals = notation.split('|')
    action = {'do': vals[0]}

    if len(vals) == 2:
        action['wait'] = int(vals[1])

    return action


def parse_utils(notn: str) -> List[Tuple[str, List]]:
    parts = notn.split('|')
    utils = parts[1:]
    parsed_utils = []

    for util in utils:
        util_parts = util.strip().split(' ')
        parsed_utils.append((util_parts[0], util_parts[1:]))

    return parsed_utils


def parse_value(notn: str) -> Tuple[str, str]:
    parts_1 = notn.split('|')
    parts_2 = parts_1[0].split('@')
    attr = parts_2[0]
    selector = ''

    if len(parts_2) > 1:
        selector = parts_2[1]

    return (attr.strip(), selector.strip())


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
        # print('#' * 50, key, v)
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
        # pprint(vars, indent=2, depth=2)
        # pprint(value, indent=2, depth=2)
        raise ValueError(Fore.RED + 'No match found at ' + Fore.CYAN + f'"{key}"' + Fore.RED + ' when operand is ' + Fore.BLUE + f'"{operand}"' + Fore.RESET)
    