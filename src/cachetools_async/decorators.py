from collections.abc import Mapping
from functools import update_wrapper
from typing import Callable, Awaitable, Union
from inspect import iscoroutinefunction
from asyncio import get_event_loop, shield, Future, Task

from cachetools import Cache
from cachetools.keys import hashkey, methodkey


PossibleCache = Union[Cache, Mapping, None]


def apply_task_result_to_future(task: Task, future: Future):
    if not task.done():
        # We aren't done yet, so we can't apply the result
        return

    if task.cancelled():
        future.cancel()
        return

    if task.exception() is not None:
        future.set_exception(task.exception())
        return

    future.set_result(task.result())


def cached(cache: PossibleCache, key=hashkey, lock=None, info=False):
    """
    Decorator to wrap a function with a memoizing callable that saves
    results in a cache.
    """

    if info:
        raise NotImplementedError("cachetools_async does not support `info`")

    if lock is not None:
        raise NotImplementedError("cachetools_async does not support `lock`")

    def decorator(fn: Callable[..., Awaitable]):
        if not iscoroutinefunction(fn):
            raise TypeError("Expected Coroutine function, got {}".format(fn))

        if cache is None:

            async def wrapper(*args, **kwargs):
                return await fn(*args, **kwargs)

            def cache_clear():
                pass

        else:

            async def wrapper(*args, **kwargs):
                k = key(*args, **kwargs)

                try:
                    future = cache[k]
                except KeyError:
                    # key not found
                    future = None

                if future is not None:
                    if not future.done():
                        return await shield(future)

                    if future.exception() is None:
                        return future.result()

                coro = fn(*args, **kwargs)

                loop = get_event_loop()

                # Crete a task that tracks the coroutine execution
                task = loop.create_task(coro)

                # Create a future and then tie the future and task together
                f = loop.create_future()
                task.add_done_callback(lambda t: apply_task_result_to_future(t, f))

                try:
                    cache[k] = f
                except ValueError:
                    # value too large
                    pass
                return await shield(f)

            def cache_clear():
                cache.clear()

        wrapper.cache = cache
        wrapper.cache_key = key
        wrapper.cache_lock = None
        wrapper.cache_clear = cache_clear
        wrapper.cache_info = None

        return update_wrapper(wrapper, fn)

    return decorator


def cachedmethod(cache: Callable[..., PossibleCache], key=methodkey):
    """
    Decorator to wrap a class or instance method with a memoizing
    callable that saves results in a cache.
    """

    def decorator(method: Callable[..., Awaitable]):
        if not iscoroutinefunction(method):
            raise TypeError("Expected Coroutine function, got {}".format(method))

        async def wrapper(self, *args, **kwargs):
            c = cache(self)
            if c is None:
                # No cache available - run the method as normal
                return await method(self, *args, **kwargs)

            k = key(self, *args, **kwargs)

            try:
                future = c[k]
            except KeyError:
                # key not found
                future = None

            if future is not None:
                if not future.done():
                    return await shield(future)

                if future.exception() is None:
                    return future.result()

            coro = method(self, *args, **kwargs)

            loop = get_event_loop()

            # Crete a task that tracks the coroutine execution
            task = loop.create_task(coro)

            # Create a future and then tie the future and task together
            future = loop.create_future()
            task.add_done_callback(lambda t: apply_task_result_to_future(t, future))

            try:
                c[k] = future
            except ValueError:
                # value too large
                pass
            return await shield(future)

        def clear(self):
            c = cache(self)
            if c is not None:
                c.clear()

        wrapper.cache = cache
        wrapper.cache_key = key
        wrapper.cache_lock = None
        wrapper.cache_clear = clear

        return update_wrapper(wrapper, method)

    return decorator
