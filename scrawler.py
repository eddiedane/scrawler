r"""**Scrawler**: Web scraping made simple—just configure and collect.

    Scrawler makes web crawling and scraping more easier.
    With simple configuration, 
    that can be provide directly or as configuration files like JSON or YAML,
    you can set your parameters and let Scrawler handle the rest.
    It’s a straightforward tool designed to get you the data you need without the hassle of coding.
"""


import json, yaml, re, os
from colorama import Fore, Style
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Locator, Page, Route, TimeoutError
from slugify import slugify
from typing import Any, Dict, List, Literal, Tuple
from utils import keypath, notation
from utils.config import validate
from utils.helpers import is_file_type, pick, is_numeric, is_none_keys


Config = Dict[Literal['browser', 'scrawl'], Dict]
NodeConfig = Dict[Literal['selector', 'all', 'range', 'links', 'data', 'nodes', 'actions', 'wait', 'contains', 'excludes'], int | str | bool | List | Dict]
LinkConfig = Dict[Literal['name', 'url', 'metadata'], str | Dict[str, Any]]
DataConfig = Dict[Literal['scope', 'value'], str | List[str] | Dict[str, Any]]
ActionConfig = Dict[Literal['type', 'delay', 'wait', 'screenshot', 'dispatch', 'count'], str | int | bool]
Link = Dict[Literal['url', 'metadata'], str | Dict[str, Any]]
Links = Dict[str, List[Link]]
DOMRect = Dict[Literal['x', 'y', 'width', 'height', 'top', 'right', 'bottom', 'left'], float]


class Scrawler():
    def __init__(self, config: Config):
        """
        Initializes a Scrawler instance.

        Args:
            config (Config): The configuration for the scrawler.

        Attributes:
            __config (Config): The validated configuration.
            __browser (Browser): The Playwright browser instance.
            __browser_context (BrowserContext): The Playwright browser context instance.
            __state (Dict): The state of the scrawler. Contains data, variables, and links.
        """
        
        self.__config = validate(config)
        self.__browser: Browser = None
        self.__browser_context: BrowserContext = None
        self.__state = {'data': {}, 'vars': {}, 'links': {}}


    def go(self):
        """
        Runs the scrawler.

        This method will block until the scrawl is finished.

        Raises:
            Exception: Any exception that is raised during the scrawl.
        """
        
        try:
            self.__scrawl()
            self.__close_browser()
        except Exception as e:
            self.__close_browser()

            raise e


    def data(self, filepath: str | None = None) -> Dict | None:
        """
        Gets the state data that was scraped during the scrawl.

        Args:
            filepath (str | None): The path to write the data to as a JSON or YAML file. If None, the data is returned as a dictionary.

        Returns:
            Dict | None: The scraped data as a dictionary, or None if a filepath was provided.

        """

        if not filepath: return self.__state['data']

        self.__output(filepath)


    def links(self, filepath: str | None = None) -> Dict | None:
        """
        Gets the links in the state that were captured during the scrawl.

        Args:
            filepath (str | None): The path to write the links to as a JSON or YAML file. If None, the links are returned as a dictionary.

        Returns:
            Dict | None: The scraped links as a dictionary, or None if a filepath was provided.
        """
        
        if not filepath: return self.__state['links']

        self.__output(filepath, state='links')
    

    @staticmethod
    def load_config(filename: str) -> Dict:
        """
        Loads a configuration file in either YAML or JSON format.

        Args:
            filename (str): The path to the configuration file to load.

        Returns:
            Dict: The loaded configuration.

        Raises:
            ValueError: If the file type is unsupported.
        """

        with open(filename, 'r') as file:
            if is_file_type('yaml', filename):
                return yaml.safe_load(file)
            elif is_file_type('json', filename):
                return json.load(file)
            
        raise ValueError(Fore.RED + 'Unable to load unsupported config file type, ' + Fore.BLUE + filename + Fore.RESET)


    def __scrawl(self) -> None:
        """
        Starts the scrawling process.

        This method will block until the scrawl is finished.

        Raises:
            Exception: Any exception that is raised during the scrawl.
        """
        
        self.__launch_browser()

        if 'scrawl' not in self.__config: return

        for pg in self.__config['scrawl']:
            links = self.__resolve_page_link(pg['link'])
            
            for link in links:
                page = self.__new_page(link['url'])
                self.__state['vars'] = link.get('metadata', {})
                self.__state['vars']['_url'] = page.url

                nodes = repeat.get('nodes', [])
                
                if 'repeat' in pg:
                    repeat = pg['repeat']

                    if 'times' in repeat:
                        for i in range(repeat['times']):
                            self.__interact(page, nodes)
                    elif 'while' in repeat:
                        while self.__should_repeat(page, repeat['while']):
                            self.__interact(page, nodes)
                else:
                    self.__interact(page, nodes)

                if self.__config.get('logging', False):
                    print(Fore.YELLOW + 'Closing page: ' + Fore.BLUE + link['url'] + Fore.RESET)

                for p in self.__browser_context.pages[1:]: p.close()


    def __output(self, filepath: str, state: str = 'data') -> None:
        """
        Writes the given state data to a file.

        Args:
            filepath (str): The path to write the data to.
            state (str, optional): The state to write. Defaults to 'data'.

        Raises:
            Exception: Any exception that occurs while writing the file.
        """
        
        if not filepath: return

        dir = os.path.dirname(filepath)
        data = self.__state[state]

        if dir: os.makedirs(dir, exist_ok=True)

        with open(filepath, 'w') as stream:

            if is_file_type('yaml', filepath):
                if self.__config.get('logging', False):
                    print(Fore.GREEN + f'Outputting {state} to YAML: ' + Fore.BLUE + filepath + Fore.RESET)

                yaml.dump(data, stream)

            if is_file_type('json', filepath):
                if self.__config.get('logging', False):
                    print(Fore.GREEN + f'Outputting {state} to JSON: ' + Fore.BLUE + filepath + Fore.RESET)

                json.dump(data, stream, indent=2, ensure_ascii=False)


    def __should_repeat(self, page: Page, opts: Dict) -> bool:
        """
        Checks if a given condition on a page is satisfied, and if so, repeats page interaction.

        Args:
            page (Page): The page to check.
            opts (Dict): The condition to check. Can contain the following keys:
                - selector (str): The selector to check.
                - exists (bool): Whether the selector should exist or not.
                - disabled (bool): Whether the selector should be disabled or not.

        Returns:
            bool: True if the condition is satisfied, False otherwise.
        """
        
        loc = page.locator(opts['selector']).first

        if 'exists' in opts and bool(loc.count()) == opts['exists']: return True

        if 'disabled' in opts and loc.is_disabled() == opts['disabled']: return True

        return False

    
    def __interact(self, page: Page, nodes: List[NodeConfig]) -> None:
        """
        Interacts with a page by executing the given nodes.

        Args:
            page (Page): The page to interact with.
            nodes (List[NodeConfig]): The nodes to interact with. Each node is a dictionary containing the following keys:
                - selector (str): The CSS selector to interact with.
                - contains (str): The text the selector should contain.
                - excludes (str): The text the selector should not contain.
                - wait (int): The time in milliseconds to wait for the selector to appear.
                - all (bool): Whether to interact with all matching selectors, or just the first one.
                - range (List[int]): The range of selectors to interact with, given as a list of three integers: start index, stop index, and step size.
                - show (bool): Whether to scroll the selector into view before interacting with it.
                - actions (List[ActionConfig]): The actions to perform on the selector.
                - links (LinkConfig): The links to extract from the selector.
                - data (DataConfig): The data to extract from the selector.
                - nodes (List[NodeConfig]): The nodes to interact with after interacting with the selector.
        """

        for alts in nodes:
            alts = alts if type(alts) == list else [alts]

            for node in alts:

                self.__state['vars']['_node'] = re.sub(':', '-', node.get('name', node['selector']))
                loc_kwargs = {}

                if 'contains' in node: loc_kwargs['has_text'] = node['contains']

                if 'excludes' in node: loc_kwargs['has_not_text'] = node['excludes']

                locator = page.locator(node['selector'], **loc_kwargs)

                if self.__config.get('logging', False):
                    print(Fore.GREEN + 'Interacting with: ' + Fore.WHITE + Style.DIM + node['selector'] + Style.NORMAL + Fore.RESET)

                if 'wait' in node:
                    try: locator.wait_for(timeout=node['wait'])
                    except TimeoutError as e: raise e

                locs = locator.all()
                count = len(locs)

                if not count: continue

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
                
                if count: break

    
    def __add_links(self, loc: Locator, links: List[LinkConfig]) -> None:
        """
        Adds links to the state.

        Args:
            loc (Locator): The Playwright locator to use for extracting the links.
            links (List[LinkConfig]): The links to add, given as a list of dictionaries containing the following keys:
                - name (str): The key to use for storing the links in the state.
                - url (str): The URL of the link.
                - metadata (Dict[str, str]): The metadata for the link, given as a dictionary of strings.

        The links are stored in the state as a list of dictionaries, each containing the keys 'url' and 'metadata'.
        """
        
        for link in links:
            name = link['name']
            metadata: Dict = {}
            result = self.__evaluate(link['url'], loc)

            if name not in self.__state['links']:
                self.__state['links'][name] = []

            if 'metadata' in link:
                for key, value in link['metadata'].items():
                    metadata[key] = self.__evaluate(value, loc)

            if type(result) is not list:
                self.__state['links'][name].append({'url': result, 'metadata': metadata})
                continue
            
            for string in result:
                self.__state['links'][name].append({'url': string, 'metadata': metadata})


    def __extract_data(self, loc: Locator, configs: List[DataConfig], all: bool = False) -> None:
        """
        Extracts data from a Playwright locator and stores it in the state.

        Args:
            loc (Locator): The Playwright locator to use for extracting the data.
            configs (List[DataConfig]): The data configurations to use for extracting the data, given as a list of dictionaries containing the following keys:
                - scope (str): The scope in the state to store the extracted data, given as a string in keypath notation.
                - value (str | List[str] | Dict[str, str]): The value to extract, given as a string, list of strings, or dictionary of strings. If a string, the value is treated as a CSS selector and the text content of the matching element is extracted. If a list of strings, the value is treated as a list of CSS selectors and the text content of all matching elements is extracted. If a dictionary, the value is treated as a dictionary of CSS selectors to attributes and the attribute values of all matching elements are extracted.
            all (bool, optional): Whether to extract all matching elements, or just the first one. Defaults to False.
        """

        for config in configs:
            value = None

            if type(config['value']) is str:
                value = self.__evaluate(config['value'], loc)
            elif type(config['value']) is list:
                value = [self.__evaluate(attr, loc) for attr in config['value']]
            elif type(config['value']) is dict:
                value = {}

                for key, attr in config['value'].items():
                    if type(attr) is str:
                        value[key] = self.__evaluate(attr, loc)
                        continue

                    value[key] = self.__attribute(attr, loc)

            value = [value] if all else value

            if type(value) is list and value[0] is None: value = []

            scope = keypath.resolve(
                config['scope'],
                self.__state['data'],
                self.__state['vars'],
                resolve_key=notation.find_item_key
            )

            if self.__config.get('logging', False):
                print(Fore.GREEN + 'Extracting data to ' + Fore.CYAN + keypath.to_string(scope) + Fore.RESET)

            keypath.assign(value, self.__state['data'], scope, merge=True)

    
    def __node_actions(self, actions: List[ActionConfig], loc: Locator) -> None:
        """
        Performs the given actions on the given locator.

        Args:
            actions (List[ActionConfig]): The actions to perform, given as a list of dictionaries containing the following keys:
                - type (str): The type of action to perform, given as a string. Supported types are 'click', 'dispatch', 'swipe_left', 'swipe_right'.
                - delay (int, optional): The time in milliseconds to wait before performing the action. Defaults to 0.
                - count (int | str, optional): The number of times to perform the action. If a string, the value is treated as a variable name and the value of the variable is used. Defaults to 1.
                - options (Dict[str, bool], optional): The options for the action, given as a dictionary containing the following keys:
                    - button (bool, optional): Whether to use the left mouse button for the action. Defaults to True.
                    - modifiers (bool, optional): Whether to use the modifier keys for the action. Defaults to True.
                - screenshot (str, optional): The file path to save a screenshot of the page to after the action, given as a string. The file path may contain variables and will be evaluated before the action is performed. Defaults to None.
                - dispatch (bool, optional): Whether to dispatch the action as an event. Defaults to False.
                - wait (int, optional): The time in milliseconds to wait after performing the action. Defaults to 0.
            loc (Locator): The locator to perform the actions on.

        Returns:
            None
        """
        
        for action in actions:
            # pre-evaluate and cache screenshot file path,
            # before the node is removed or made inaccessible by action event
            screenshot_path = ''

            if 'screenshot' in action: screenshot_path = self.__evaluate(action['screenshot'], loc)

            count = action.get('count', 1)

            if type(count) is str: count = self.__evaluate(count, loc)

            t: str = action['type']
            rect: DOMRect = loc.evaluate("node => node.getBoundingClientRect()")

            for _ in range(count):
                if 'delay' in action: loc.page.wait_for_timeout(action['delay'])

                if not loc.is_visible() and self.__config.get('logging', False):
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

    
    def __evaluate(self, string: str, loc: Locator) -> str | List[str]:
        """
        Evaluates a string with variables and attribute getters and returns the result.

        This function takes a string and a Locator object as input and returns a string
        with all variables and attribute getters replaced with their respective values.

        The string may contain variables and attribute getters in the following format:
        - $var{var_name}: Replaced with the value of the variable var_name.
        - $attr{attr_name}: Replaced with the value of the attribute attr_name of the Locator.

        The function uses the notation.parse_getters function to parse the string and
        extract the variables and attribute getters. It then iterates over the getters and
        replaces each getter with its respective value in the string.

        Args:
            string (str): The string to evaluate.
            loc (Locator): The Locator object to use for evaluating the string.

        Returns:
            str | List[str]: The evaluated string.
        """
        
        getters = notation.parse_getters(string)

        for full_match, typ, var_name in getters:
            value = full_match

            match typ:
                case 'attr': value = self.__attribute(var_name, loc)
                case 'var': value = str(self.__var(var_name, full_match))

            string = re.sub(re.escape(full_match), value, string)

        return string
    

    def __apply_utils(self, utils: List[Tuple[str, List]], val: str):   
        """
        Applies a list of utilities to a given value.

        The list of utilities is a list of tuples, where the first element of the tuple is the name of the utility and the second element is a list of arguments to the utility.

        The utilities are applied in order, and the value is updated after each utility is applied.

        The supported utilities are:

        - prepend: Prepends the given argument to the value.
        - lowercase: Converts the value to lowercase.
        - slug: Converts the value to a slug.
        - subtract: Subtracts the given argument from the value.
        - clear_url_params: Removes any URL parameters from the value.
        - trim: Trims any whitespace from the value.

        Args:
            utils (List[Tuple[str, List]]): The list of utilities to apply.
            val (str): The value to apply the utilities to.

        Returns:
            str: The value after applying the utilities.
        """
        
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
                case 'trim':
                    value = value.strip()
        
        return value
    

    def __var(self, name: str, default: Any = None) -> Any:
        """
        Gets a variable from the state by name.

        Args:
            name (str): The name of the variable to get.
            default (Any): The default value to return if the variable is not set.

        Returns:
            Any: The value of the variable, or default if the variable is not set.
        """
        
        result = notation.parse_value(name, set_defaults=False)

        if not is_none_keys(result, 'child_node', 'ctx', 'max', 'selector'):
            raise ValueError(Fore.RED + 'Invalid $var{...} notation at ' + Fore.CYAN + name + Fore.RESET)

        if result['prop'] in self.__state['vars']:
            return self.__apply_utils(result['parsed_utils'], self.__state['vars'][name])
        
        return default
    
    
    def __attribute(self, node_attr: str, loc: Locator) -> str | List:
        """
        Extracts an attribute from a locator and applies utilities to it.

        Args:
            node_attr (str): The attribute to extract, given as a string in notation format.
            loc (Locator): The Playwright locator to use for extracting the attribute.

        Returns:
            str | List: The extracted attribute value, or a list of values if the attribute is extracted from multiple nodes.
        """
        
        values = []
        utils = []
        locs = [loc]
        result = notation.parse_value(node_attr)
        attr = result['prop']
        child_node = result['child_node']
        selector = result['selector']
        max = result['max']
        ctx = result['ctx']
        utils = result['parsed_utils']
        var_name = result['var']

        if not attr : raise ValueError(Fore.RED + 'Attribute to extract not define at ' + Fore.WHITE + (selector or self.__state['vars']['_node']) + Fore.RESET)

        if selector:
            match ctx:
                case 'parent': locs = loc.locator(selector).all()
                case 'page': locs = loc.page.locator(selector).all()

        if attr == 'count': return int(self.__apply_utils(utils, len(locs)))

        if max == 'one': locs = locs[0:1]

        for loc in locs:
            value = None

            if attr in ['href', 'src', 'text']:
                if attr == 'text': attr = 'textContent'

                value = loc.evaluate(f'(node, [childNode, attr]) => childNode ? node.childNodes[childNode - 1][attr] : node[attr]', [child_node, attr])

            if len(utils): 
                value = self.__apply_utils(utils, value)

            values.append(value)

        if max == 'one': values: str = dict(enumerate(values)).get(0, '')

        if var_name: self.__state['vars'][var_name] = values

        return values
        

    def __launch_browser(self) -> None:
        """
        Launches a Playwright browser instance.

        This function launches a Playwright browser instance using the configuration
        provided in the 'browser' key of the scrawler configuration. The browser type
        is determined by the 'type' key, which may be 'chromium', 'firefox', or 'webkit'.
        The 'show' key controls whether the browser is launched in headless mode, and
        the 'slowdown' key controls the slowdown time in milliseconds.

        Args:
            None

        Returns:
            None
        """
        
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


    def __close_browser(self) -> None:
        """
        Closes the Playwright browser instance.

        This function closes the Playwright browser instance launched by the Scrawler.

        Args:
            None

        Returns:
            None
        """
        
        if self.__config.get('logging', False):
            print(Fore.YELLOW + 'Closing browser' + Fore.RESET)

        self.__browser_context.pages[0].close()
        self.__browser_context.close()
        self.__browser.close()


    def __new_page(self, url: str) -> Page:
        """
        Opens a new page and configures it according to the browser configuration.

        Args:
            url (str): The URL to open the page with.

        Returns:
            Page: The opened page.
        """
        
        if self.__config.get('logging', False):
            print(Fore.GREEN + Style.BRIGHT + 'Opening a new page: ' + Style.NORMAL + Fore.BLUE + url + Fore.RESET)

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
        """
        Blocks a request if its resource type is in the given types.

        Args:
            route (Route): The route to block.
            types (List[str]): The resource types to block.
        """
        
        if route.request.resource_type in types:
            route.abort()
        else:
            route.continue_()
    
    
    def __resolve_page_link(self, url: str | Dict | List[str | Dict]) -> List:
        """
        Resolves a given URL or list of URLs to a list of links.

        Args:
            url (str | Dict | List[str | Dict]): The URL or list of URLs to resolve.

        Returns:
            List[Dict]: The resolved list of links, where each link is a dictionary containing the keys 'url' and 'metadata'.
        """
        
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
        """
        Resolves a given range to a tuple of three integers.

        The range can be given as a list of up to three integers, or as a string of the form 'start:stop:step'.
        The start and stop values are inclusive, and the step value defaults to 1.
        The special value '_' can be used to indicate that the start, stop, or step value should be omitted.

        Args:
            range (List): The range to resolve.
            max (int): The maximum value that the resolved range can have.

        Returns:
            Tuple[int, int, int]: The resolved range as a tuple of three integers.
        """
        
        rng = dict(enumerate(range))
        rng_start: int = rng.get(0, 0)
        rng_start = 0 if rng_start == '_' else rng_start
        rng_stop: int = rng.get(1, max)
        rng_stop = max if rng_stop == '_' else rng_stop
        rng_step: int = rng.get(2, 1)
        rng_step = 1 if rng_step == '_' else rng_step

        return (rng_start, rng_stop, rng_step)