import asyncio

import pytest

from openchronicle_new.infrastructure.adapters.cache_inmemory import InMemoryCache


@pytest.mark.asyncio
async def test_set_get_roundtrip():
    cache = InMemoryCache()
    await cache.set("a", 1)
    assert await cache.get("a") == 1


@pytest.mark.asyncio
async def test_expiration():
    cache = InMemoryCache()
    await cache.set("a", 1, ttl=0.1)
    await asyncio.sleep(0.2)
    assert await cache.get("a") is None
