from functools import update_wrapper
from typing import (
    TypeVar,
    Callable,
    Awaitable,
    Any,
    MutableMapping,
    Optional,
    ContextManager,
)
from inspect import iscoroutinefunction
from asyncio import get_event_loop, shield, Future, Task

from cachetools.keys import hashkey, methodkey


_KT = TypeVar("_KT")


def apply_task_result_to_future(task: Task, future: Future):
    if task.cancelled():
        future.cancel()
        return

    exception = task.exception()
    if exception is not None:
        future.set_exception(exception)
        return

    future.set_result(task.result())


def cached(
    cache: Optional[MutableMapping[_KT, Future]],
    key: Callable[..., _KT] = hashkey,
    lock: Optional[ContextManager[Any]] = None,
    info: bool = False,
):
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

        async def wrapper(*args, **kwargs):
            k = key(*args, **kwargs)

            try:
                future = cache[k] if cache is not None else None
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
                if cache is not None:
                    cache[k] = f
            except ValueError:
                # value too large
                pass
            return await shield(f)

        def cache_clear():
            if cache is not None:
                cache.clear()

        setattr(wrapper, "cache", cache)
        setattr(wrapper, "cache_key", key)
        setattr(wrapper, "cache_lock", None)
        setattr(wrapper, "cache_clear", cache_clear)
        setattr(wrapper, "cache_info", None)

        return update_wrapper(wrapper, fn)

    return decorator


def cachedmethod(
    cache: Callable[[Any], Optional[MutableMapping[_KT, Future]]],
    key: Callable[[Any], _KT] = methodkey,
    lock: Optional[Callable[[Any], ContextManager[Any]]] = None,
):
    """
    Decorator to wrap a class or instance method with a memoizing
    callable that saves results in a cache.
    """

    if lock is not None:
        raise NotImplementedError("cachetools_async does not support `lock`")

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

        def cache_clear(self):
            c = cache(self)
            if c is not None:
                c.clear()

        setattr(wrapper, "cache", cache)
        setattr(wrapper, "cache_key", key)
        setattr(wrapper, "cache_lock", None)
        setattr(wrapper, "cache_clear", cache_clear)

        return update_wrapper(wrapper, method)

    return decorator
