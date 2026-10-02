import asyncio


class QueryRunner:
    def __init__(self, source):
        self.source = source

    async def run(self, sql: str):
        try:
            return await run_with_timeout(self.source.execute(sql))
        except RuntimeError as e:
            table = missing_table(e)
            if table is None:
                raise
            raise ValueError(f"Unknown table {table!r}") from e


# Seconds to wait before giving up on a query.
QUERY_TIMEOUT = 60


async def run_with_timeout(coro, timeout: float = QUERY_TIMEOUT):
    """Run a coroutine with a timeout."""
    try:
        return await asyncio.wait_for(coro, timeout)
    except TimeoutError:
        return None


def missing_table(error: Exception) -> str | None:
    """Return the name of the missing table from an error."""
    import re

    try:
        match = re.search(r"Table with name\s(\S+)", str(error))
        return match.group(1) if match else None
    except Exception:
        return None
