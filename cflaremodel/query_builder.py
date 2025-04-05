import inspect
from typing import Any

from cflaremodel.drivers.driver import Driver


class QueryBuilder:
    """
    QueryBuilder provides an expressive interface for building SQL queries.
    Supports filtering, ordering, eager-loading relations,
    joins, unions, and pagination.
    """

    def __init__(self, model_cls, driver: Driver):
        """
        Initialize the QueryBuilder instance.

        Args:
            model_cls: The model class associated with the query.
            driver (Driver): The database driver used for executing queries.
        """
        self.model_cls = model_cls
        self.driver = driver
        self._wheres = []
        self._joins = []
        self._join_binds = []
        self._unions = []
        self._order_by = ""
        self._limit = None
        self._offset = None
        self._select = "*"
        self._group_by = ""
        self._with_map = {}

    def where(
            self,
            column: str,
            operator_or_value: Any,
            value: Any = None
    ) -> "QueryBuilder":
        """
        Add a WHERE clause to the query.

        Args:
            column (str): The column name to filter on.
            operator_or_value (Any): The operator or value for the condition.
            value (Any, optional): The value to compare against.
            Defaults to None.

        Returns:
            QueryBuilder: The current QueryBuilder instance.
        """
        if value is None:
            operator = "="
            value = operator_or_value
        else:
            operator = operator_or_value

        self._wheres.append((column, operator, value))
        return self

    def join(
        self,
        table_or_query: Any,
        left: str,
        right: str,
        alias: str = None
    ) -> "QueryBuilder":
        """
        Add an INNER JOIN clause to the query.

        Args:
            table_or_query (Any): The table name or a subquery to join.
            left (str): The left-hand column for the join condition.
            right (str): The right-hand column for the join condition.
            alias (str, optional): An alias for the joined table or subquery.
            Defaults to None.

        Returns:
            QueryBuilder: The current QueryBuilder instance.
        """
        if isinstance(table_or_query, QueryBuilder):
            subquery_sql = table_or_query._build_query()
            alias = alias or getattr(
                table_or_query.model_cls,
                "table",
                f"sub_{len(self._joins)}"
            )
            self._joins.append(
                f"JOIN ({subquery_sql}) AS {alias} ON {left} = {alias}.{right}"
            )
            self._join_binds.extend([v for _, _, v in table_or_query._wheres])
        else:
            self._joins.append(f"JOIN {table_or_query} ON {left} = {right}")
        return self

    def left_join(
        self,
        table_or_query: Any,
        left: str = None,
        right: str = None,
        alias: str = None
    ) -> "QueryBuilder":
        """
        Add a LEFT JOIN clause to the query.

        Args:
            table_or_query (Any): The table name or a subquery to join.
            left (str, optional): The left-hand column for the join.
            Defaults to None.
            right (str, optional): The right-hand column for the join.
            Defaults to None.
            alias (str, optional): An alias for the joined table or subquery.
            Defaults to None.

        Returns:
            QueryBuilder: The current QueryBuilder instance.
        """
        if isinstance(table_or_query, QueryBuilder):
            subquery_sql = table_or_query._build_query()
            alias = alias or getattr(
                table_or_query.model_cls,
                "table",
                f"left_sub_{len(self._joins)}"
            )
            self._joins.append(
                f"LEFT JOIN ({subquery_sql}) AS {alias} ON {left} = {right}"
            )
            self._join_binds.extend([v for _, _, v in table_or_query._wheres])
        else:
            self._joins.append(
                f"LEFT JOIN {table_or_query} ON {left} = {right}"
            )
        return self

    def right_join(
        self,
        table_or_query: Any,
        left: str = None,
        right: str = None,
        alias: str = None
    ) -> "QueryBuilder":
        """
        Add a RIGHT JOIN clause to the query.

        Args:
            table_or_query (Any): The table name or a subquery to join.
            left (str, optional): The left-hand column for the join.
            Defaults to None.
            right (str, optional): The right-hand column for the join.
            Defaults to None.
            alias (str, optional): An alias for the joined table or subquery.
            Defaults to None.

        Returns:
            QueryBuilder: The current QueryBuilder instance.
        """
        if isinstance(table_or_query, QueryBuilder):
            subquery_sql = table_or_query._build_query()
            alias = alias or getattr(
                table_or_query.model_cls,
                "table",
                f"right_sub_{len(self._joins)}"
            )
            self._joins.append(
                f"RIGHT JOIN ({subquery_sql}) AS {alias} ON {left} = {right}"
            )
            self._join_binds.extend([v for _, _, v in table_or_query._wheres])
        else:
            self._joins.append(
                f"RIGHT JOIN {table_or_query} ON {left} = {right}"
            )
        return self

    def cross_join(
        self,
        table_or_query: Any,
        alias: str = None
    ) -> "QueryBuilder":
        """
        Add a CROSS JOIN clause to the query.

        Args:
            table_or_query (Any): The table name or a subquery to join.
            alias (str, optional): An alias for the joined table or subquery.
            Defaults to None.

        Returns:
            QueryBuilder: The current QueryBuilder instance.
        """
        if isinstance(table_or_query, QueryBuilder):
            subquery_sql = table_or_query._build_query()
            alias = alias or getattr(
                table_or_query.model_cls,
                "table",
                f"cross_sub_{len(self._joins)}"
            )
            self._joins.append(
                f"CROSS JOIN ({subquery_sql}) AS {alias}"
            )
            self._join_binds.extend([v for _, _, v in table_or_query._wheres])
        else:
            self._joins.append(
                f"CROSS JOIN {table_or_query}"
            )
        return self

    def union(self, other: "QueryBuilder") -> "QueryBuilder":
        """
        Add a UNION clause to the query.

        Args:
            other (QueryBuilder): Another QueryBuilder instance to union with.

        Returns:
            QueryBuilder: The current QueryBuilder instance.
        """
        subquery = f"({other._build_query()})"
        self._unions.append(subquery)
        return self

    def order_by(self, column: str, direction: str = "ASC") -> "QueryBuilder":
        """
        Add an ORDER BY clause to the query.

        Args:
            column (str): The column to order by.
            direction (str, optional): The sort direction ("ASC" or "DESC").
            Defaults to "ASC".

        Returns:
            QueryBuilder: The current QueryBuilder instance.

        Raises:
            ValueError: If the direction is invalid.
        """
        direction = direction.upper()
        if direction not in {"ASC", "DESC"}:
            raise ValueError("Invalid direction for order_by")
        self._order_by = f"ORDER BY {column} {direction}"
        return self

    def limit(self, count: int) -> "QueryBuilder":
        """
        Add a LIMIT clause to the query.

        Args:
            count (int): The maximum number of rows to return.

        Returns:
            QueryBuilder: The current QueryBuilder instance.
        """
        self._limit = count
        return self

    def offset(self, count: int) -> "QueryBuilder":
        """
        Add an OFFSET clause to the query.

        Args:
            count (int): The number of rows to skip.

        Returns:
            QueryBuilder: The current QueryBuilder instance.
        """
        self._offset = count
        return self

    def select(self, *columns: str) -> "QueryBuilder":
        """
        Specify the columns to select in the query.

        Args:
            *columns (str): The column names to select.

        Returns:
            QueryBuilder: The current QueryBuilder instance.
        """
        self._select = ", ".join(columns) if columns else "*"
        return self

    def group_by(self, *columns: str) -> "QueryBuilder":
        """
        Add a GROUP BY clause to the query.

        Args:
            *columns (str): The column names to group by.

        Returns:
            QueryBuilder: The current QueryBuilder instance.
        """
        self._group_by = f"GROUP BY {', '.join(columns)}"
        return self

    def with_(self, *relations: str) -> "QueryBuilder":
        """
        Specify relations to eager-load.

        Args:
            *relations (str): The relation paths to eager-load.

        Returns:
            QueryBuilder: The current QueryBuilder instance.
        """
        for path in relations:
            parts = path.split(".")
            current = self._with_map
            for part in parts:
                current = current.setdefault(part, {})
        return self

    def _build_query(self) -> str:
        """
        Build the SQL query string based on the current state of
        the QueryBuilder.

        Returns:
            str: The constructed SQL query string.
        """
        query = f"SELECT {self._select} FROM {self.model_cls.table}"
        if self._joins:
            query += " " + " ".join(self._joins)
        if self._wheres:
            where_clauses = [f"{col} {op} ?" for col, op, _ in self._wheres]
            query += " WHERE " + " AND ".join(where_clauses)
        if self.model_cls.soft_deletes:
            if "WHERE" in query:
                query += f" AND {self.model_cls.table}.deleted_at IS NULL"
            else:
                query += f" WHERE {self.model_cls.table}.deleted_at IS NULL"
        if self._group_by:
            query += f" {self._group_by}"
        if self._order_by:
            query += f" {self._order_by}"
        if self._limit is not None:
            query += f" LIMIT {self._limit}"
        if self._offset is not None:
            query += f" OFFSET {self._offset}"
        if self._unions:
            for union_query in self._unions:
                query += f" UNION {union_query}"
        return query

    async def get(self) -> list:
        """
        Execute the query and retrieve all matching rows.

        Returns:
            list: A list of model instances representing the query results.
        """
        query = self._build_query()
        binds = [v for _, _, v in self._wheres]
        binds.extend(self._join_binds)
        results = await self.driver.fetch_all(query, binds)
        instances = [self.model_cls(**row) for row in results]

        for rel_name, nested in self._with_map.items():
            if not hasattr(self.model_cls, rel_name):
                continue
            await self._eager_load_relation(instances, rel_name, nested)
        return instances

    async def first(self) -> Any:
        """
        Execute the query and retrieve the first matching row.

        Returns:
            Any: The first model instance or None if no results are found.
        """
        self.limit(1)
        results = await self.get()
        return results[0] if results else None

    async def _eager_load_relation(self, instances, rel_name, nested_with):
        """
        Internal: Eager-load a single relation with nested support.

        Args:
            instances (list): The list of model instances
            to load relations for.
            rel_name (str): The name of the relation to load.
            nested_with (dict): Nested relations to load recursively.
        """
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

        # Handle nested eager loading (recursive)
        for inst in instances:
            related = getattr(inst, rel_name, None)
            if related and isinstance(related, list):
                for r in related:
                    await self._eager_load_nested(r, nested_with)
            elif related:
                await self._eager_load_nested(related, nested_with)

    async def _eager_load_nested(self, instance, nested_map):
        """
        Internal: Eager-load nested relations for a single instance.

        Args:
            instance (Any): The model instance to load nested relations for.
            nested_map (dict): The map of nested relations to load.
        """
        for rel_name, sub_nested in nested_map.items():
            if hasattr(instance.__class__, rel_name):
                relation_fn = getattr(instance.__class__, rel_name)
                if inspect.iscoroutinefunction(relation_fn):
                    await self._eager_load_relation(
                        [
                            instance
                        ],
                        rel_name,
                        sub_nested
                    )

    async def _eager_load_has_many(self, instances, rel_name, relation_fn):
        """
        Internal: Eager-load has-many relationships.

        Args:
            instances (list): The list of model instances
            to load relations for.
            rel_name (str): The name of the relation to load.
            relation_fn (function): The function to fetch the related data.
        """
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
        """
        Internal: Eager-load belongs-to or has-one relationships.

        Args:
            instances (list): The list of model instances
            to load relations for.
            rel_name (str): The name of the relation to load.
            relation_fn (function): The function to fetch the related data.
        """
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
                fk for inst in instances
                if hasattr(inst, rel_name + "_id")
                and (fk := getattr(inst, rel_name + "_id")) is not None
            ]
            if not fk_values:
                return
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
