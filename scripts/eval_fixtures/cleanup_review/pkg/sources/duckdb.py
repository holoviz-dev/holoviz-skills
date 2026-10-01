import re

MISSING_TABLE_RE = re.compile(r"Table with name\s(\S+)")


def missing_table_name(error: Exception) -> str | None:
    match = MISSING_TABLE_RE.search(str(error))
    return match.group(1) if match else None


class DuckDBSource:
    def __init__(self, connection):
        self.connection = connection

    async def execute(self, sql: str):
        return self.connection.execute(sql).fetchall()
