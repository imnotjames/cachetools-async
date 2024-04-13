import asyncio
from unittest.mock import AsyncMock, MagicMock, call

import cachetools_async
import pytest


class ExampleClass:
    async def identity(self, *args, **kwargs):
        return (self, ) + args + tuple(kwargs.items())

    async def cancel_self(self):
        task = asyncio.current_task()
        task.cancel()
        return self

    def not_coroutine(self):
        raise NotImplementedError()


def test_cachedmethod_raises_type_error_without_coroutine():
    decorator = cachetools_async.cachedmethod(lambda _: None)

    with pytest.raises(TypeError, match="Expected Coroutine"):
        decorator(ExampleClass.not_coroutine)


async def test_cachedmethod_full_cache_never_caches():
    # Set up a cache that's always empty and never empty
    cache_mock = MagicMock()
    cache_mock.__getitem__.return_value = None
    cache_mock.__setitem__.side_effect = ValueError()

    cache_resolver = MagicMock()
    cache_resolver.return_value = cache_mock

    mock = AsyncMock()
    mock.func.return_value = "bar"

    decorated_fn = cachetools_async.cachedmethod(cache_resolver)(mock.func)

    actual = await asyncio.gather(
        *(
            decorated_fn(mock, "foo")
            for _ in range(5)
        ),
    )

    mock.func.assert_has_calls([call(mock, "foo")] * 5)
    assert len(mock.func.mock_calls) == 5
    assert actual == ["bar"] * 5


class TestCachedmethodDict:
    @pytest.fixture()
    def mock_resolver(self):
        mock_resolver = MagicMock()
        mock_resolver.return_value = {}
        yield mock_resolver

    async def test_params_are_passed_through(self, mock_resolver):
        decorated_fn = cachetools_async.cachedmethod(mock_resolver)(ExampleClass.identity)

        example = ExampleClass()

        assert await decorated_fn(example, 0) == (example, 0,)
        assert await decorated_fn(example, "foo") == (example, "foo",)
        assert await decorated_fn(example, "foo", bar="baz") == (example, "foo", ("bar", "baz"))

    async def test_multiple_calls(self, mock_resolver):
        mock = AsyncMock()

        mock.func.return_value = "bar"
        decorated_fn = cachetools_async.cachedmethod(mock_resolver)(mock.func)

        actual = await asyncio.gather(
            *(
                decorated_fn(mock, "foo")
                for _ in range(5)
            ),
            *(
                decorated_fn(mock, "bar")
                for _ in range(5)
            )
        )

        mock.func.assert_has_calls([call(mock, "foo"), call(mock, "bar")])
        assert len(mock.mock_calls) == 2
        assert actual == ["bar"] * 10

    async def test_cancelled_calls_are_propagated(self, mock_resolver):
        decorated_fn = cachetools_async.cachedmethod(mock_resolver)(ExampleClass.cancel_self)

        call_future = decorated_fn(ExampleClass())

        with pytest.raises(asyncio.CancelledError):
            await call_future

    async def test_completed_future(self, mock_resolver):
        mock = AsyncMock()

        mock.func.return_value = "bar"
        decorated_fn = cachetools_async.cachedmethod(mock_resolver)(mock.func)

        await decorated_fn(mock, "foo")
        await decorated_fn(mock, "bar")

        actual = await decorated_fn(mock, "foo")

        mock.func.assert_has_calls([call(mock, "foo"), call(mock, "bar")])
        assert len(mock.func.mock_calls) == 2
        assert actual == "bar"

    async def test_does_not_cache_exceptions(self, mock_resolver):
        mock = AsyncMock()

        mock.func.side_effect = [
            TypeError(),
            "example",
        ]

        decorated_fn = cachetools_async.cachedmethod(mock_resolver)(mock.func)

        with pytest.raises(TypeError):
            await decorated_fn(mock)

        assert await decorated_fn(mock) == "example"

    async def test_cache_clear_evicts_everything(self, mock_resolver):
        mock = AsyncMock()
        mock.return_value = "bar"

        decorated_fn = cachetools_async.cachedmethod(mock_resolver)(mock)

        await decorated_fn("foo")
        await decorated_fn("foo")

        decorated_fn.cache_clear("foo")

        actual = await decorated_fn("foo")

        mock.assert_has_calls([call("foo"), call("foo")])
        assert len(mock.mock_calls) == 2
        assert actual == "bar"

    async def test_cache_clear_passes_to_resolver(self, mock_resolver):
        decorated_fn = cachetools_async.cachedmethod(mock_resolver)(ExampleClass.identity)

        decorated_fn.cache_clear("example")

        mock_resolver.assert_called_with("example")


class TestCachedNone:
    async def test_params_are_passed_through(self):
        decorated_fn = cachetools_async.cachedmethod(lambda _: None)(ExampleClass.identity)

        example = ExampleClass()

        assert await decorated_fn(example, 0) == (example, 0,)
        assert await decorated_fn(example, "foo") == (example, "foo",)
        assert await decorated_fn(example, "foo", bar="baz") == (example, "foo", ("bar", "baz"))

    async def test_cache_clear(self):
        decorated_fn = cachetools_async.cachedmethod(lambda _: None)(ExampleClass.identity)

        assert hasattr(decorated_fn, "cache_clear")
        assert callable(decorated_fn.cache_clear)

        # It's a no-op but call it anyway
        decorated_fn.cache_clear(ExampleClass())

    async def test_extra_properties_are_set(self):
        decorated_fn = cachetools_async.cachedmethod(lambda _: None)(ExampleClass.identity)

        assert hasattr(decorated_fn, "cache")
        assert hasattr(decorated_fn, "cache_key")
        assert hasattr(decorated_fn, "cache_lock")
        assert hasattr(decorated_fn, "cache_clear")