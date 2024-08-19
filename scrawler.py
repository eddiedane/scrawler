r"""Scrawler simplifies scraping on the web"""


import json, yaml, re, os
from colorama import Fore
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Locator, Page, Route, TimeoutError
from slugify import slugify
from typing import Any, Dict, List, Literal, Tuple
from utils import keypath, notation
from utils.config import validate
from utils.helpers import is_file_type, flatten_list, pick


Config = Dict[Literal['browser', 'scrawl'], Dict]
Action = Dict[Literal['type', 'delay', 'wait', 'screenshot', 'dispatch'], str | int | bool]


class Scrawler():
    def __init__(self, config: Config):
        self.__config = validate(config)
        self.__browser: Browser = None
        self.__browser_context: BrowserContext = None
        self.__state = {'data': {}, 'vars': {}, 'links': {}}


    def go(self):
        self.__scrawl()


    def data(self, filepath: str = None) -> Dict | None:
        if not filepath: return self.__state['data']

        return self.__output(filepath)
    

    @staticmethod
    def load_config(filename: str) -> Dict:
        with open(filename, 'r') as file:
            if is_file_type('yaml', filename):
                return yaml.safe_load(file)
            elif is_file_type('json', filename):
                return json.load(file)
            
        raise ValueError(Fore.RED + 'Unable to load unsupported config file type, ' + Fore.BLUE + filename + Fore.RESET)


    def __scrawl(self):
        self.__launch_browser()

        if 'scrawl' not in self.__config or 'pages' not in self.__config['scrawl']: return

        for pg in self.__config['scrawl']['pages']:
            links = self.__resolve_page_link(pg['link'])
            
            for link in links:
                print(Fore.GREEN + 'Opening a new page: ' + Fore.BLUE + link['url'] + Fore.RESET)

                page = self.__new_page(link['url'])
                self.__state['vars'] = link.get('metadata', {})
                self.__state['vars']['_url'] = page.url

                if 'repeat' in pg:
                    repeat = pg['repeat']

                    if 'times' in repeat:
                        for i in range(repeat['times']):
                            self.__interact(page, repeat['nodes'])
                    elif 'while' in repeat:
                        while not self.__should_repeat(page, repeat['while']):
                            self.__interact(page, repeat['nodes'])
                else:
                    self.__interact(page, pg['nodes'])

                print(Fore.YELLOW + 'Closing page: ' + Fore.BLUE + link['url'] + Fore.RESET)

                page.close()

        print(Fore.YELLOW + 'Closing browser' + Fore.RESET)
        self.__browser_context.close()
        self.__browser.close()


    def __output(self, filepath: str):
        if not filepath: return

        dir = os.path.dirname(filepath)
        data = self.__state['data']

        if dir: os.makedirs(dir, exist_ok=True)

        with open(filepath, 'w') as stream:

            if is_file_type('yaml', filepath):
                print(Fore.GREEN + 'Outputing data to YAML: ' + Fore.BLUE + filepath + Fore.RESET)
                yaml.dump(data, stream)

            if is_file_type('json', filepath):
                print(Fore.GREEN + 'Outputing data to JSON: ' + Fore.BLUE + filepath + Fore.RESET)
                json.dump(data, stream, indent=2, ensure_ascii=False)


    def __should_repeat(self, page: Page, opts: Dict) -> bool:
        loc = page.locator(opts['selector']).first

        if 'exists' in opts and bool(loc.count()) == opts['exists']: return True
        
        if 'disabled' in opts and loc.is_disabled() == opts['disabled']: return True

        return False

    
    def __interact(self, page: Page, nodes: List[Dict]):
        for node in nodes:
            print(Fore.GREEN + 'Interacting with: ' + Fore.WHITE + node['selector'] + Fore.RESET)
            
            self.__state['vars']['_node'] = re.sub(':', '-', node.get('name', node['selector']))
            locs = page.locator(node['selector']).all()
            all: bool = node.get('all', False)
            rng_start, rng_stop, rng_step = self.__resolve_range(node.get('range', []), len(locs))
            locs = locs[rng_start:rng_stop]
            scroll_into_view = node.get('show', False)

            if not all: locs = locs[0:1]

            extracted_links = []
            extracted_data = []

            for i in range(0, len(locs), rng_step):
                self.__state['vars']['_nth'] = i
                loc = locs[i]

                if scroll_into_view: loc.scroll_into_view_if_needed()

                self.__node_actions(node.get('actions', []), loc)

                if 'extract' in node and 'links' in node['extract']:
                    extracted_links.append(self.__extract_link(loc, node['extract']['links']))

                if 'extract' in node and 'data' in node['extract']:
                    extracted_data.append(self.__extract_data(loc, node['extract']['data']))

                if 'nodes' in node:
                    self.__interact(page, node['nodes'])
            
            if 'extract' in node:
                self.__save_extract(
                    node['extract'],
                    extracted_links,
                    extracted_data,
                    node.get('all', False)
                )

    
    def __extract_link(self, loc: Locator, opts: Dict) -> Dict:
        link = {
            'url': self.__evaluate(opts['value'], loc, simplified_attr=True),
            'metadata': {}
        }

        if 'metadata' in opts:
            for key, val_notn in opts['metadata'].items():
                link['metadata'][key] = self.__evaluate(val_notn, loc, simplified_attr=True)
                
        return link


    def __extract_data(self, loc: Locator, opts: Dict) -> str | List | Dict:
        value = None

        if type(opts['value']) is str:
            value = self.__evaluate(opts['value'], loc, simplified_attr=True)
        elif type(opts['value']) is list:
            value = [self.__evaluate(attr, loc, simplified_attr=True) for attr in opts['value']]
        elif type(opts['value']) is dict:
            value = {key: self.__evaluate(attr, loc, simplified_attr=True) for key, attr in opts['value'].items()}

        return value
    

    def __save_extract(self, ext: Dict, links: List, data_values: List, all: bool = True) -> None:
        if 'links' in ext:
            print(Fore.GREEN + 'Extracting links' + Fore.RESET)
            if keypath.has_key(self.__state['links'], ext['links']['name']):
                self.__state['links'][ext['links']['name']] = self.__state['links'][ext['links']['name']] + links
            else:
                self.__state['links'][ext['links']['name']] = links
    
        if 'data' in ext:
            print(Fore.GREEN + 'Extracting data' + Fore.RESET)
            data = self.__state['data']
            path = keypath.resolve(
                ext['data']['name'],
                data,
                self.__state['vars'],
                special_key=r'\*\{(\w+)(=|!=|>=|<=|>|<)(\$)?(\w+)\}',
                resolve_key=notation.find_item_key
            )
            value = data_values if all else data_values[0]

            keypath.assign(value, data, path, merge=True)

    
    def __node_actions(self, actions: List[Action], loc: Locator):
        """Perform listed actions on the selected node"""
        
        for action in actions:
            # pre-evaluate and cache screenshot file path,
            # before the node is removed or made inaccesible by action event
            screenshot_path = ''

            if 'screenshot' in action:
                screenshot_path = self.__evaluate(action['screenshot'], loc)

            if 'delay' in action:
                loc.page.wait_for_timeout(action['delay'])

            if action.get('dispatch', False):
                loc.dispatch_event(action['type'])
            else:
                if not loc.is_visible():
                    print(Fore.YELLOW + 'Action may fail due to node being inaccessible or not visible: ' + Fore.WHITE + f'{self.__state['vars']['_node']}@{action['type']}')
                match action['type']:
                    case 'click':
                        loc.click(**pick(action.get('options', {}), {
                            'button': True,
                            'modifiers': True,
                        }))
                    case _:
                        raise ValueError(f'The "{action['do']}" is not supported')
                    
            if 'wait' in action:
                loc.page.wait_for_timeout(action['wait'])

            if 'screenshot' in action:
                loc.page.screenshot(path=screenshot_path, full_page=True)

    
    def __evaluate(self, string: str, loc: Locator, simplified_attr: bool = False) -> str:
        """Replace all variable notations in given string with values"""

        placeholder_re = r'(\$(var|attr)\{\s*(_?[^|}]+(?:\s*\|\s*\w+(?:\s+[^\s{}]+)*)*\s*)\})'
        var_names: List = set(re.findall(placeholder_re, string))
        
        if simplified_attr and not len(var_names):
            return self.__attribute(string, loc)

        for notn, typ, var_name in var_names:
            value = notn

            match typ:
                case 'attr':
                    value = self.__attribute(var_name, loc)
                case 'var':
                    value = str(self.__var(var_name, notn))

            string = re.sub(
                re.escape(notn),
                value,
                string
            )

        return string
    

    def __apply_utils(self, utils: List[Tuple[str, List]], val: str):   
        value = val

        for name, args in utils:
            match name.strip():
                case 'prepend':
                    if len(args) > 0:
                        value = f'{args[0]}{value or ''}'
                case 'lowercase':
                    value = str(value).lower()
                case 'slug':
                    value = slugify(str(value))
        
        return value
    

    def __var(self, name: str, default: Any = None) -> Any:
        utils, name = notation.parse_utils(name)
        if name in self.__state['vars']:
            return self.__apply_utils(utils, self.__state['vars'][name])
        
        return default
    
    
    def __attribute(self, node_attr: str | Dict, loc: Locator) -> str | None:
        values = []
        utils = []
        locs = [loc]

        if type(node_attr) is str:
            all = False
            utils, node_attr = notation.parse_utils(node_attr)
            attr, selector = notation.parse_value(node_attr)
            node_attr = {'attribute': attr, 'selector': selector or None}
        else:
            all = node_attr.get('all', False)
            attr = node_attr.get('attribute', '')
            utils, _ = notation.parse_utils(attr)
            selector = node_attr.get('selector', None)

        if not attr : raise ValueError(f'Attribute to extract not define at {loc}')

        if selector:
            locs = loc.locator(selector).all()

        if not all: locs = locs[0:1]

        for loc in locs:
            value = None
            try:
                if attr in ['href', 'src']:
                    value = loc.get_attribute(attr)
                elif attr == 'text':
                    value = loc.inner_text()
            except TimeoutError as e:
                selector = selector if selector else self.__state['vars']['_node']
                raise TimeoutError(Fore.RED + 'Node is inaccessible or not visible: ' + Fore.MAGENTA + f'{selector}' + Fore.RESET)

            if len(utils): 
                value = self.__apply_utils(utils, value)

            values.append(value)

        if not all: return dict(enumerate(values)).get(0, '')

        return values
        

    def __launch_browser(self):
        playwright = sync_playwright().start()
        browser_type: str = self.__config['browser']['type'] or 'chromium'

        if not hasattr(playwright, browser_type):
            raise ValueError(Fore.RED + 'Unsupported or invalid browser type, ' + Fore.CYAN + browser_type + Fore.RESET)
        
        kwargs = {}

        if keypath.get('browser.show', self.__config):
            kwargs['headless'] = not self.__config['browser']['show']
        
        if 'slowdown' in self.__config['browser']:
            kwargs['slow_mo'] = self.__config['browser']['slowdown']

        self.__browser = getattr(playwright, browser_type).launch(**kwargs)
        self.__browser_context = self.__browser.new_context()


    def __new_page(self, url: str) -> Page:
        page = self.__browser_context.new_page()
        viewport: List = keypath.get('browser.viewport', self.__config, [])
        blacklisted_resources: List = keypath.get('browser.block', self.__config, [])

        if len(viewport) == 2:
            page.set_viewport_size({
                'width': viewport[0],
                'height': viewport[1]
            })

        if len(blacklisted_resources):
            page.route(
                '**/*',
                lambda route: self.__block_request(route, blacklisted_resources)
            )

        kwargs = {}

        if 'ready_on' in self.__config['browser']:
            kwargs['wait_until'] = self.__config['browser']['ready_on']

        if 'timeout' in self.__config['browser']:
            kwargs['timeout'] = self.__config['browser']['timeout']
        
        page.goto(url, **kwargs)

        return page


    def __block_request(self, route: Route, types: List[str]) -> None:  
        if route.request.resource_type in types:
            route.abort()
        else:
            route.continue_()
    
    
    def __resolve_page_link(self, url: str | Dict | List[str | Dict]) -> List:
        urls: List[str | dict] = [url] if type(url) in [str, dict] else url
        links: List[Dict] = []

        for url in urls:
            if type(url) is dict:
                links.append(url)
            elif url[0] == '$':
                links += self.__state['links'].get(url[1:], [])
            else:
                links.append({'url': url, 'metadata': {}})

        return links
    
    
    def __resolve_range(self, range: List, max: int) -> Tuple[int, int, int]:
        rng = dict(enumerate(range))
        rng_start: int = rng.get(0, 0)
        rng_start = 0 if rng_start == '_' else rng_start
        rng_stop: int = rng.get(1, max)
        rng_stop = max if rng_stop == '_' else rng_stop
        rng_step: int = rng.get(2, 1)
        rng_step = 1 if rng_step == '_' else rng_step

        return (rng_start, rng_stop, rng_step)