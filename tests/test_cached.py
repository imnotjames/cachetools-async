import asyncio
from unittest.mock import AsyncMock, call

import cachetools_async
import pytest


async def identity(*args, **kwargs):
    return args + tuple(kwargs.items())


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
            *(
                decorated_fn("foo")
                for _ in range(5)
            ),
            *(
                decorated_fn("bar")
                for _ in range(5)
            )
        )

        mock.assert_has_calls([call("foo"), call("bar")])
        assert len(mock.mock_calls) == 2
        assert actual == ["bar"] * 10

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
