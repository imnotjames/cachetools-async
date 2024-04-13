import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, call

import cachetools_async
import pytest


async def identity(*args, **kwargs):
    return args + tuple(kwargs.items())


def test_cached_fails_unimplemented_features():
    with pytest.raises(NotImplementedError, match="does not support `info`"):
        cachetools_async.cached(None, info=True)

    # Not quite an actual lock but close enough for the test
    class FakeLock(contextlib.AbstractContextManager):
        def __exit__(self, __exc_type, __exc_value, __traceback):
            pass

    with pytest.raises(NotImplementedError, match="does not support `lock`"):
        cachetools_async.cached(None, lock=FakeLock)


def test_cached_raises_type_error_without_coroutine():
    def simple():
        pass

    decorator = cachetools_async.cached(None)

    with pytest.raises(TypeError, match="Expected Coroutine"):
        decorator(simple)

    with pytest.raises(TypeError, match="Expected Coroutine"):
        decorator(10)

    with pytest.raises(TypeError, match="Expected Coroutine"):
        decorator({})


async def test_cached_full_cache_never_caches():
    # Set up a cache that's always empty and never empty
    cache_mock = MagicMock()
    cache_mock.__getitem__.return_value = None
    cache_mock.__setitem__.side_effect = ValueError()

    mock = AsyncMock()
    mock.return_value = "bar"

    decorated_fn = cachetools_async.cached(cache_mock)(mock)

    actual = await asyncio.gather(
        *(decorated_fn("foo") for _ in range(5)),
    )

    mock.assert_has_calls([call("foo")] * 5)
    assert len(mock.mock_calls) == 5
    assert actual == ["bar"] * 5


class TestCachedDict:
    async def test_params_are_passed_through(self):
        decorated_fn = cachetools_async.cached({})(identity)

        assert await decorated_fn(0) == (0,)
        assert await decorated_fn("foo") == ("foo",)
        assert await decorated_fn("foo", bar="baz") == ("foo", ("bar", "baz"))

    async def test_multiple_calls(self):
        mock = AsyncMock()

        mock.return_value = "bar"
        decorated_fn = cachetools_async.cached({})(mock)

        actual = await asyncio.gather(
            *(decorated_fn("foo") for _ in range(5)),
            *(decorated_fn("bar") for _ in range(5)),
        )

        mock.assert_has_calls([call("foo"), call("bar")])
        assert len(mock.mock_calls) == 2
        assert actual == ["bar"] * 10

    async def test_cancelled_calls_are_propagated(self):
        async def func():
            task = asyncio.current_task()
            task.cancel()

        decorated_fn = cachetools_async.cached({})(func)

        call_future = decorated_fn()

        with pytest.raises(asyncio.CancelledError):
            await call_future

    async def test_completed_future(self):
        mock = AsyncMock()

        mock.return_value = "bar"
        decorated_fn = cachetools_async.cached({})(mock)

        await decorated_fn("foo")
        await decorated_fn("bar")

        actual = await decorated_fn("foo")

        mock.assert_has_calls([call("foo"), call("bar")])
        assert len(mock.mock_calls) == 2
        assert actual == "bar"

    async def test_does_not_cache_exceptions(self):
        mock = AsyncMock()

        mock.side_effect = [
            TypeError(),
            "example",
        ]

        decorated_fn = cachetools_async.cached({})(mock)

        with pytest.raises(TypeError):
            await decorated_fn()

        assert await decorated_fn() == "example"

    async def test_cache_clear_evicts_everything(self):
        mock = AsyncMock()

        mock.return_value = "bar"
        decorated_fn = cachetools_async.cached({})(mock)

        await decorated_fn("foo")
        await decorated_fn("foo")

        decorated_fn.cache_clear()

        actual = await decorated_fn("foo")

        mock.assert_has_calls([call("foo"), call("foo")])
        assert len(mock.mock_calls) == 2
        assert actual == "bar"


class TestCachedNone:
    async def test_params_are_passed_through(self):
        decorated_fn = cachetools_async.cached(None)(identity)

        assert await decorated_fn(0) == (0,)
        assert await decorated_fn("foo") == ("foo",)
        assert await decorated_fn("foo", bar="baz") == ("foo", ("bar", "baz"))

    async def test_cache_clear(self):
        decorated_fn = cachetools_async.cached(None)(identity)

        assert hasattr(decorated_fn, "cache_clear")
        assert callable(decorated_fn.cache_clear)

        # It's a no-op but call it anyway
        decorated_fn.cache_clear()

    async def test_extra_properties_are_set(self):
        decorated_fn = cachetools_async.cached(None)(identity)

        assert hasattr(decorated_fn, "cache")
        assert hasattr(decorated_fn, "cache_key")
        assert hasattr(decorated_fn, "cache_lock")
        assert hasattr(decorated_fn, "cache_clear")
        assert hasattr(decorated_fn, "cache_info")
