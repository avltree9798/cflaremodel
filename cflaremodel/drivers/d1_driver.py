from cflaremodel.drivers.driver import Driver


class D1Driver(Driver):
    def __init__(self, db):
        self.db = db

    async def fetch_one(self, query, params):
        stmt = self.db.prepare(query)
        result = await stmt.bind(*params).first()
        if result is None:
            return None
        return result.to_py()

    async def fetch_all(self, query, params):
        stmt = self.db.prepare(query)
        result = await stmt.bind(*params).all()
        return [row.to_py() for row in result.results if row is not None]

    async def execute(self, query, params):
        stmt = self.db.prepare(query)
        return await stmt.bind(*params).run()
