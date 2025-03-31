import inspect
from typing import Any

from cflaremodel.drivers.driver import Driver


class QueryBuilder:
    """
    QueryBuilder provides an expressive interface for building SQL queries.
    Supports filtering, ordering, eager-loading relations, and pagination.
    """

    def __init__(self, model_cls, driver: Driver):
        """Initialise QueryBuilder with model class and driver."""
        self.model_cls = model_cls
        self.driver = driver
        self._wheres = []
        self._order_by = ""
        self._with = []
        self._limit = None
        self._offset = None
        self._select = "*"
        self._group_by = ""

    def where(self,
              column: str,
              operator_or_value: Any,
              value: Any = None
              ) -> "QueryBuilder":
        """
        Add a where clause to the query.

        Supports:
        - where("email", "like", "%example.com")
        - where("id", 123)  → shorthand for where("id", "=", 123)
        """
        if value is None:
            # where("id", 123)
            operator = "="
            value = operator_or_value
        else:
            operator = operator_or_value

        self._wheres.append((column, operator, value))
        return self

    def order_by(self, column: str, direction: str = "ASC") -> "QueryBuilder":
        """Specify order of the results."""
        direction = direction.upper()
        if direction not in {"ASC", "DESC"}:
            raise ValueError("Invalid direction for order_by")
        self._order_by = f"ORDER BY {column} {direction}"
        return self

    def limit(self, count: int) -> "QueryBuilder":
        """Limit the number of returned rows."""
        self._limit = count
        return self

    def offset(self, count: int) -> "QueryBuilder":
        """Offset the result set by a number of rows."""
        self._offset = count
        return self

    def select(self, *columns: str) -> "QueryBuilder":
        """Select specific columns from the table."""
        self._select = ", ".join(columns) if columns else "*"
        return self

    def group_by(self, *columns: str) -> "QueryBuilder":
        """Group results by specified columns."""
        self._group_by = f"GROUP BY {', '.join(columns)}"
        return self

    def with_(self, *relations: str) -> "QueryBuilder":
        """Eager-load relationships."""
        self._with.extend(relations)
        return self

    async def _eager_load_relation(self, instances, rel_name):
        """Internal: Eager-load a single relation name."""
        if not instances:
            return

        sample_instance = instances[0]
        rel_method = getattr(type(sample_instance), rel_name, None)

        if not rel_method or not inspect.iscoroutinefunction(rel_method):
            return

        bound = rel_method.__get__(sample_instance, type(sample_instance))
        relation_result = await bound()

        if isinstance(relation_result, list):
            await self._eager_load_has_many(instances, rel_name, rel_method)
        elif relation_result is None:
            return
        else:
            await self._eager_load_single(instances, rel_name, rel_method)

    async def _eager_load_has_many(self, instances, rel_name, relation_fn):
        """Internal: Eager-load has-many relationships."""
        sample_instance = instances[0]
        bound = relation_fn.__get__(sample_instance, type(sample_instance))
        sample_result = await bound()

        if not sample_result or not isinstance(sample_result, list):
            return

        related_cls = sample_result[0].__class__
        foreign_key = None

        for field in sample_result[0].__dict__:
            if field.endswith('_id') and hasattr(sample_instance, 'id'):
                foreign_key = field
                break

        if not foreign_key:
            return

        local_ids = [
            getattr(inst, 'id')
            for inst in instances
            if hasattr(inst, 'id')
        ]
        if not local_ids:
            return

        placeholders = ",".join(["?"] * len(local_ids))
        query = f"SELECT * FROM {related_cls.table} \
            WHERE {foreign_key} \
                IN ({placeholders})"
        results = await self.driver.fetch_all(query, local_ids)

        grouped = {}
        for row in results:
            key = row[foreign_key]
            grouped.setdefault(key, []).append(related_cls(**row))

        for inst in instances:
            inst_id = getattr(inst, "id", None)
            setattr(inst, rel_name, grouped.get(inst_id, []))

    async def _eager_load_single(self, instances, rel_name, relation_fn):
        """Internal: Eager-load belongs-to or has-one relationships."""
        sample_instance = instances[0]
        relation_result = await relation_fn.__get__(
            sample_instance,
            type(sample_instance)
        )()

        if relation_result is None:
            return

        related_cls = relation_result.__class__

        if hasattr(relation_result, "id"):
            owner_key = "id"
            fk_values = [
                getattr(inst, rel_name + "_id")
                for inst in instances
                if hasattr(inst, rel_name + "_id")
            ]
        else:
            return

        if not fk_values:
            return

        placeholders = ",".join(["?"] * len(fk_values))
        query = f"SELECT * FROM {related_cls.table} \
            WHERE {owner_key} \
                IN ({placeholders})"
        results = await self.driver.fetch_all(query, fk_values)

        related_map = {row[owner_key]: related_cls(**row) for row in results}

        for inst in instances:
            fk = getattr(inst, rel_name + "_id", None)
            setattr(inst, rel_name, related_map.get(fk))

    async def get(self):
        """Execute the built query and return model instances."""
        query = f"SELECT {self._select} FROM {self.model_cls.table}"
        binds = []

        if self._wheres:
            where_clauses = [f"{col} {op} ?" for col, op, _ in self._wheres]
            query += " WHERE " + " AND ".join(where_clauses)
            binds.extend([v for _, _, v in self._wheres])

        if self.model_cls.soft_deletes:
            if "WHERE" in query:
                query += " AND deleted_at IS NULL"
            else:
                query += " WHERE deleted_at IS NULL"

        if self._group_by:
            query += f" {self._group_by}"

        if self._order_by:
            query += f" {self._order_by}"

        if self._limit is not None:
            query += f" LIMIT {self._limit}"

        if self._offset is not None:
            query += f" OFFSET {self._offset}"

        results = await self.driver.fetch_all(query, binds)
        instances = [self.model_cls(**row) for row in results]

        for rel_name in self._with:
            if not hasattr(self.model_cls, rel_name):
                continue
            await self._eager_load_relation(instances, rel_name)

        return instances
