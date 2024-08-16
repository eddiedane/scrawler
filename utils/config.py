from colorama import Fore
from typing import Dict

def validate(config: Dict) -> Dict:
    def list_of(typ, lst):
        if not lst: return False
        for itm in lst:
            if type(itm) is not typ: return False
        return True

    if 'browser' in config:
        b = config['browser']

        if 'type' in b and type(b['type']) is not str:
            raise ValueError(Fore.RED + 'Invalid configuration value at ' + Fore.CYAN + 'browser.type, ' + Fore.RED + 'expected a string')
        
        if 'show' in b and type(b['show']) is not bool:
            raise ValueError(Fore.RED + 'Invalid configuration value at ' + Fore.CYAN + 'browser.show, ' + Fore.RED + 'expected and boolean')
        
        if 'slowdown' in b and type(b['slowdown']) is not int:
            raise ValueError(Fore.RED + 'Invalid configuration value at ' + Fore.CYAN + 'browser.slowdown, ' + Fore.RED + 'expected and integer')
        
        if 'viewport' in b and (not list_of(int, b['viewport']) or len(b['viewport']) != 2):
            raise ValueError(Fore.RED + 'Invalid configuration value at ' + Fore.CYAN + 'browser.viewport, ' + Fore.RED + 'expected a list with two integers')
        
        if 'block' in b and not list_of(str, b['block']):
            raise ValueError(Fore.RED + 'Invalid configuration value at ' + Fore.CYAN + 'browser.block, ' + Fore.RED + 'expected a list of strings')
    
    
    return config