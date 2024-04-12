# cachetools_async

[![Latest pypi version](https://img.shields.io/pypi/v/cachetools_async)](https://pypi.org/project/cachetools_async/)
[![Test Coverage](https://img.shields.io/codecov/c/github/imnotjames/cachetools_async/master.svg)](https://codecov.io/gh/imnotjames/cachetools_async)
[![License](https://img.shields.io/github/license/imnotjames/cachetools_async)](./LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


This module provides decorators for Python asyncio coroutine functions
to support memoization.  These are compatible, and can be considered extending
the functionality of `cachetools`.

```python
from cachetools import LRUCache, TTLCache
from cachetools_async import cached

# Dependencies for our examples
import aiohttp
import python_weather

# cache least recently used Python Enhancement Proposals
@cached(cache=LRUCache(maxsize=32))
async def get_pep(num: int):
    pep_url = 'http://www.python.org/dev/peps/pep-%04d/' % num
    async with aiohttp.ClientSession() as session:
        async with session.get(pep_url) as response:
            return await response.text()


# cache weather data for no longer than ten minutes
@cached(cache=TTLCache(maxsize=1024, ttl=600))
async def get_weather(place):
    async with python_weather.Client(unit=python_weather.METRIC) as client:
        return await client.get(place)
```

This module supports the same definition of a cache as cachetools does - a mutable mapping of a fixed
maximum size.  The cache itself is not asynchronous, even when the functions that are being cached are.

Note that once you call a function once, subsequent calls before the initial call completes will wait
until the first complete.  To help understand this, take the example from before.  However, let's imagine
we need to get weather for multiple locations at once, too.

```python
from cachetools import LRUCache, TTLCache
from cachetools_async import cached
import asyncio
import python_weather

@cached(cache=TTLCache(maxsize=1024, ttl=600))
async def get_weather(place):
    async with python_weather.Client(unit=python_weather.METRIC) as client:
        return await client.get(place)

async def get_multiple_weather(places):
    return await asyncio.gather(
        get_weather(place)
        for place in places
    )

get_multiple_weather([
    "New York",
    "London",
    "London",
    "Miami",
    "New York",
    "Miami",
    "London",
    "New York",
])
```

Even though they all occur in parallel with 8 weather reports, the `cached` decorator will ensure
only 3 requests for weather would actually be made.

## Installation

`cachetools_async` is available via PyPi and can be installed as such in your package manager of choice.

### Poetry

```shell
poetry add cachetools_async
```

### Rye

```shell
rye add "cachetools_async"
```

### Pip

```shell
pip install cachetools_async
```


## License

Licensed under the [MIT License](./LICENSE).