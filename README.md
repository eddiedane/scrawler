# Scrawler

**Web scraping made simple — just configure and collect.**

Scrawler makes web crawling and scraping more easier. With simple configuration, that can be provide directly or as configuration files like JSON or YAML, you can set your parameters and let Scrawler handle the rest. It’s a straightforward tool designed to get you the data you need without the hassle of coding.

### Usage/Examples

```python
from scrawler import Scrawler

config = Scrawler.load_config('example.scrawler.yaml')
scrawler = Scrawler(config)

scrawler.go()
# get the scraped data as dictionary
data = scrawler.data()
# dump the data to a file
scrawler.data('dumps/example.data.json')
```

### Configuration for Scrawler

The Scrawler class requires a configuration object to guide its web scraping behavior. Below is a description of the configuration options.

### Root-Level Keys:
- **browser**: `Dict` Contains settings related to the browser's behavior.
    - **type**: `str` Supported browser type i.e. `chromium` as the default, `webkit` or `firefox`
    - **show**: `bool`
    - **timeout**: `int`
    - **slowdown**: `int` The amount of milliseconds to slowdown browser interaction
    - **ready_on**: `str` `load` (default), `domcontentloaded`,  `networkidle`, or `commit`
    - **viewport**: `List[int]`
    - **block**: `List[str]` Resource types to block

- **logging**: `bool` Enable or disable logging info on the terminal

- **scrawl**: `List[Dict]` A list of page configurations, each dictating how to interact with a specific web page.
    - Example:
      ```yaml
      scrawl:
        - link: https://example.com
          nodes:
            - selector: H1
            ...
        ...
      ```

### Page Configuration (within `scrawl`):
- **link**: `Dict | str | List[Dict]`
- **repeat**: `Dict`
- **nodes**: `List[Dict]`

- **nodes**: `List[Dict]` Defines a list of elements to interact with on the page.
    - **selector**: `str`
    - **all**: `bool`
    - **range**: `List[int]`
    - **contain**: `str`
    - **excludes**: `str`
    - **show**: `show`
    - **wait**: `int`
    - **actions**: `List[Dict]`
    - **links**: `List[Dict]`
    - **data**: `List[Dict]`
    - **nodes**: `List[Dict]`

### Node Configuration:
- **selector**: `str`
    - CSS selector for the element to interact with.
    - Example: `".item"`

- **contains**: `str`
    - Optional text that the selected element must contain.
    - Example: `"Buy Now"`

- **excludes**: `str`
    - Optional text that the selected element must not contain.
    - Example: `"Out of Stock"`

- **wait**: `int`
    - Time in milliseconds to wait for the selector to appear.
    - Example: `500`

- **all**: `bool`
    - Whether to interact with all matching elements or just the first one.
    - Example: `true`

- **range**: `List[int]`
    - Range of selectors to interact with, defined as `[start, stop, step]`.
    - Example: `[0, 10, 1]`

- **show**: `bool`
    - Whether to scroll the selector into view before interacting with it.
    - Example: `true`

- **actions**: `List[Dict]`
    - A list of actions to perform on the selected element.
    - Example:
      ```yaml
      actions:
        - type: "click"
        - wait: 500
      ```

- **links**: `Dict`
    - Specifies links to extract from the selected element.
    - Example:
      ```yaml
      links:
        name: "product_link"
        url: "$attr{href}"
      ```

- **data**: `List[Dict]`
    - Defines data extraction configurations.
    - Example:
      ```yaml
      data:
        - scope: "products"
          value: ".product-name"
      ```

- **nodes**: `List[Dict]`
    - A list of sub-nodes to interact with after interacting with the current node.
    - Example:
      ```yaml
      nodes:
        - selector: ".sub-item"
          actions:
            - type: "click"
      ```

### Action Configuration:
- **type**: `str`
    - Type of action to perform (e.g., `click`, `dispatch`, `swipe_left`, `swipe_right`).
    - Example: `"click"`

- **delay**: `int`
    - Time in milliseconds to wait before performing the action.
    - Example: `100`

- **count**: `int | str`
    - Number of times to perform the action. Can also reference a variable.
    - Example: `2`

- **options**: `Dict[str, bool]`
    - Additional options for the action (e.g., `button`, `modifiers`).
    - Example:
      ```yaml
      options:
        button: "left"
        modifiers: "ctrl"
      ```

- **screenshot**: `str`
    - Path to save a screenshot of the page after performing the action.
    - Example: `"/screenshots/page1.png"`

- **dispatch**: `bool`
    - Whether to dispatch the action as an event.
    - Example: `true`

- **wait**: `int`
    - Time in milliseconds to wait after performing the action.
    - Example: `300`