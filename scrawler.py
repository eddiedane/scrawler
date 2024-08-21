r"""Scrawler simplifies scraping on the web"""


import json, yaml, re, os
from colorama import Fore
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Locator, Page, Route, TimeoutError
from slugify import slugify
from typing import Any, Dict, List, Literal, Tuple
from utils import keypath, notation
from utils.config import validate
from utils.helpers import is_file_type, pick, is_numeric


Config = Dict[Literal['browser', 'scrawl'], Dict]
NodeConfig = Dict[Literal['selector', 'all', 'range', 'links', 'data', 'nodes', 'actions'], str | bool | List | Dict]
LinkConfig = Dict[Literal['name', 'url', 'metadata'], str | Dict[str, Any]]
DataConfig = Dict[Literal['scope', 'value'], str | List[str] | Dict[str, Any]]
ActionConfig = Dict[Literal['type', 'delay', 'wait', 'screenshot', 'dispatch', 'count'], str | int | bool]
Link = Dict[Literal['url', 'metadata'], str | Dict[str, Any]]
Links = Dict[str, List[Link]]
DOMRect = Dict[Literal['x', 'y', 'width', 'height', 'top', 'right', 'bottom', 'left'], float]


class Scrawler():
    def __init__(self, config: Config):
        self.__config = validate(config)
        self.__browser: Browser = None
        self.__browser_context: BrowserContext = None
        self.__state = {'data': {}, 'vars': {}, 'links': {}}


    def go(self):
        try:
            self.__scrawl()
            self.__close_browser()
        except Exception as e:
            self.__close_browser()

            raise e


    def data(self, filepath: str | None = None) -> Dict | None:
        if not filepath: return self.__state['data']

        self.__output(filepath)


    def links(self, filepath: str | None = None) -> Dict | None:
        if not filepath: return self.__state['links']

        self.__output(filepath, state='links')
    

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
                    nodes = repeat.get('nodes', [])

                    if 'times' in repeat:
                        for i in range(repeat['times']):
                            self.__interact(page, nodes)
                    elif 'while' in repeat:
                        while self.__should_repeat(page, repeat['while']):
                            self.__interact(page, nodes)
                else:
                    self.__interact(page, pg.get('nodes', []))

                print(Fore.YELLOW + 'Closing page: ' + Fore.BLUE + link['url'] + Fore.RESET)

                for p in self.__browser_context.pages[1:]: p.close()


    def __output(self, filepath: str, state: str = 'data'):
        if not filepath: return

        dir = os.path.dirname(filepath)
        data = self.__state[state]

        if dir: os.makedirs(dir, exist_ok=True)

        with open(filepath, 'w') as stream:

            if is_file_type('yaml', filepath):
                print(Fore.GREEN + f'Outputing {state} to YAML: ' + Fore.BLUE + filepath + Fore.RESET)
                yaml.dump(data, stream)

            if is_file_type('json', filepath):
                print(Fore.GREEN + f'Outputing {state} to JSON: ' + Fore.BLUE + filepath + Fore.RESET)
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
            locator = page.locator(node['selector'])

            try: locator.wait_for(timeout=node.get('timeout', 30000))
            except: pass

            locs = locator.all()
            all: bool = node.get('all', False)
            rng_start, rng_stop, rng_step = self.__resolve_range(node.get('range', []), len(locs))
            locs = locs[rng_start:rng_stop]
            scroll_into_view = node.get('show', False)

            if not all: locs = locs[0:1]

            for i in range(0, len(locs), rng_step):
                self.__state['vars']['_nth'] = i
                loc = locs[i]

                if scroll_into_view: loc.scroll_into_view_if_needed()

                self.__node_actions(node.get('actions', []), loc)

                if 'links' in node: self.__add_links(loc, node['links'])

                if 'data' in node: self.__extract_data(loc, node['data'], all)

                if 'nodes' in node: self.__interact(page, node['nodes'])

    
    def __add_links(self, loc: Locator, links: List[LinkConfig]) -> None:
        """Add links to state links"""

        for link in links:
            name = link['name']
            metadata: Dict = {}
            result = self.__evaluate(link['url'], loc, simplified_attr=True)

            if name not in self.__state['links']:
                self.__state['links'][name] = []

            if 'metadata' in link:
                for key, value in link['metadata'].items():
                    metadata[key] = self.__evaluate(value, loc, simplified_attr=True)

            if type(result) is not list:
                self.__state['links'][name].append({'url': result, 'metadata': metadata})
                continue
            
            for string in result:
                self.__state['links'][name].append({'url': string, 'metadata': metadata})


    def __extract_data(self, loc: Locator, configs: List[DataConfig], all: bool = False) -> None:
        for config in configs:
            value = None

            if type(config['value']) is str:
                value = self.__evaluate(config['value'], loc, simplified_attr=True)
            elif type(config['value']) is list:
                value = [self.__evaluate(attr, loc, simplified_attr=True) for attr in config['value']]
            elif type(config['value']) is dict:
                value = {}

                for key, attr in config['value'].items():
                    if type(attr) is str:
                        value[key] = self.__evaluate(attr, loc, simplified_attr=True)
                        continue

                    value[key] = self.__attribute(attr, loc)

            print(Fore.GREEN + 'Extracting data' + Fore.RESET)

            value = [value] if all else value

            if type(value) is list and value[0] is None: value = []

            scope = keypath.resolve(
                config['scope'],
                self.__state['data'],
                self.__state['vars'],
                special_key=r'\*\{(\w+)(=|!=|>=|<=|>|<)(\$)?(\w+)\}',
                resolve_key=notation.find_item_key
            )

            keypath.assign(value, self.__state['data'], scope, merge=True)

    
    def __node_actions(self, actions: List[ActionConfig], loc: Locator):
        """Perform listed actions on the selected node"""
        
        for action in actions:
            # pre-evaluate and cache screenshot file path,
            # before the node is removed or made inaccesible by action event
            screenshot_path = ''

            if 'screenshot' in action: screenshot_path = self.__evaluate(action['screenshot'], loc)

            count = action.get('count', 1)

            if type(count) is str: count = self.__evaluate(count, loc, simplified_attr=True)

            t: str = action['type']
            rect: DOMRect = loc.evaluate("node => node.getBoundingClientRect()")

            for _ in range(count):
                if 'delay' in action: loc.page.wait_for_timeout(action['delay'])

                if not loc.is_visible():
                    print(Fore.YELLOW + 'Action may fail due to node being inaccessible or not visible: ' + Fore.WHITE + f'{self.__state['vars']['_node']}@{action['type']}')
                
                if action.get('dispatch', False) and t not in ['swipe_left', 'swipe_right']:
                    loc.dispatch_event(action['type'])
                elif t == 'click':
                    loc.click(**pick(action.get('options', {}), {
                        'button': True,
                        'modifiers': True,
                    }))
                elif t in ['swipe_left', 'swipe_right']:
                    if t == 'swipe_left':
                        start_x, end_x = (rect['x'] + rect['width']/2, 0)
                    else:
                        start_x, end_x = (rect['x'] + rect['width']/2, rect['x'] + rect['width'])
                        
                    start_y = end_y = rect['y'] + rect['height']/2
                    mouse = loc.page.mouse

                    mouse.move(start_x, start_y)
                    mouse.down()
                    mouse.move(end_x, end_y)
                    mouse.up()
                else:
                    raise ValueError(Fore.RED + 'The ' + Fore.CYAN + t + Fore.RED + ' action is currently not supported' + Fore.RESET)
                        
                if 'wait' in action: loc.page.wait_for_timeout(action['wait'])

            if 'screenshot' in action: loc.page.screenshot(path=screenshot_path, full_page=True)

    
    def __evaluate(self, string: str, loc: Locator, simplified_attr: bool = False) -> str | List[str]:
        """Replace all variable notations in given string with values"""

        getters = notation.parse_getters(string)

        if simplified_attr and not len(getters):
            return self.__attribute(string, loc)

        for notn, typ, var_name in getters:
            value = notn

            match typ:
                case 'attr': value = self.__attribute(var_name, loc)
                case 'var': value = str(self.__var(var_name, notn))

            string = re.sub(re.escape(notn), value, string)

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
                case 'subtract':
                    if is_numeric(value): value = float(value)
                    else: value = 0.0

                    if len(args) > 0 and is_numeric(args[0]):
                        value = float(value) - float(args[0])
                case 'clear_url_params':
                    value = value.split('?')[0]
        
        return value
    

    def __var(self, name: str, default: Any = None) -> Any:
        result = notation.parse_value(name)

        if result['prop'] in self.__state['vars']:
            return self.__apply_utils(result['parsed_utils'], self.__state['vars'][name])
        
        return default
    
    
    def __attribute(self, node_attr: str | Dict, loc: Locator) -> str | None:
        values = []
        utils = []
        locs = [loc]
        result = notation.parse_value(node_attr)
        attr, selector, max, ctx, utils = (result['prop'], result['selector'], result['max'] or 'one', result['ctx'], result['parsed_utils'])

        if not attr : raise ValueError(Fore.RED + 'Attribute to extract not define at ' + Fore.WHITE + (selector or self.__state['vars']['_node']) + Fore.RESET)

        if selector:
            match ctx:
                case 'parent': locs = loc.locator(selector).all()
                case 'page': locs = loc.page.locator(selector).all()

        if attr == '_count': return int(self.__apply_utils(utils, len(locs)))

        if max == 'one': locs = locs[0:1]

        for loc in locs:
            value = None
            try:
                if attr in ['href', 'src']:
                    value = loc.evaluate(f'node => node.{attr}')
                elif attr == 'text':
                    value = loc.inner_text()
            except TimeoutError as e:
                selector = selector if selector else self.__state['vars']['_node']
                raise TimeoutError(Fore.RED + 'Node is inaccessible or not visible: ' + Fore.MAGENTA + f'{selector}' + Fore.RESET)

            if len(utils): 
                value = self.__apply_utils(utils, value)

            values.append(value)

        if max == 'one': return dict(enumerate(values)).get(0, '')

        return values
        

    def __launch_browser(self):
        playwright = sync_playwright().start()
        browser_config = self.__config.get('browser', {})
        browser_type: str = browser_config.get('type', 'chromium')

        if not hasattr(playwright, browser_type):
            raise ValueError(Fore.RED + 'Unsupported or invalid browser type, ' + Fore.CYAN + browser_type + Fore.RESET)
        
        kwargs = {}

        if 'show' in browser_config:
            kwargs['headless'] = not browser_config['show']
        
        if 'slowdown' in browser_config:
            kwargs['slow_mo'] = browser_config['slowdown']

        self.__browser = getattr(playwright, browser_type).launch(**kwargs)
        self.__browser_context = self.__browser.new_context()


    def __close_browser(self):
        print(Fore.YELLOW + 'Closing browser' + Fore.RESET)

        self.__browser_context.pages[0].close()
        self.__browser_context.close()
        self.__browser.close()


    def __new_page(self, url: str) -> Page:
        page = self.__browser_context.new_page()
        browser_config = self.__config.get('browser', {})
        viewport: List = browser_config.get('viewport', [])
        blacklisted_resources: List = browser_config.get('block', [])

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

        if 'ready_on' in browser_config:
            kwargs['wait_until'] = browser_config['ready_on']

        if 'timeout' in browser_config:
            kwargs['timeout'] = browser_config['timeout']
        
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
                # exclude internally set keys e.g. parent
                links.append(pick(url, {"url", "metadata"}))
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