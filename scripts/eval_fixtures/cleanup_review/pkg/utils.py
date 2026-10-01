import asyncio


async def with_timeout(coro, timeout_seconds: float = 10, default_value=None):
    try:
        return await asyncio.wait_for(coro, timeout_seconds)
    except TimeoutError:
        return default_value


def chunked(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]
