r"""Scrawler simplifies scraping on the web"""


import json, yaml
from colorama import Fore
from playwright.sync_api import sync_playwright, Browser, BrowserContext, BrowserType, Page, Route
from utils import keypath
from utils.config import validate
from utils.helpers import is_file_type
from typing import Dict, List, Literal


Config = Dict[Literal['browser', 'scrawl'], Dict]


class Scrawler():
    def __init__(self, config: Config):
        self.__config = validate(config)
        self.__browser: Browser = None
        self.__browser_context: BrowserContext = None
        self.__state = {'data': {}, 'vars': {}, 'links': {}}


    def go(self):
        self.__scrawl()
    

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

        for pg in self.__config['scrawl']:
            print(pg)


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