import json
from datetime import datetime

from cflaremodel.query_builder import QueryBuilder


class Model:
    """
    Base model class for interacting with database tables.
    Provides casting, soft deletes, relationship helpers,
    and basic CRUD operations.
    """

    table = None
    fillable = []
    guarded = []
    hidden = []
    rules = {}
    soft_deletes = True
    casts = {}
    driver = None

    def __iter__(self):
        """
        Iterate over the model instance's attributes as key-value pairs.

        Returns:
            Iterator: An iterator over the model's attributes.
        """
        return iter(self.to_dict().items())

    def to_dict(self):
        """
        Serialise the model instance to a dictionary excluding hidden fields.

        Returns:
            dict: A dictionary representation of the model instance.
        """
        default_fields = {
            "env",
            "driver",
            "table",
            "fillable",
            "guarded",
            "hidden",
            "rules",
            "casts",
            "soft_deletes"
        }

        def serialise(value):
            if isinstance(value, Model):
                return value.to_dict()
            elif isinstance(value, list):
                return [serialise(item) for item in value]
            return value

        return {
            k: serialise(v)
            for k, v in self.__dict__.items()
            if not k.startswith("_")
            and k not in self.hidden
            and k not in default_fields
        }

    def __repr__(self):
        """
        Return a pretty-printed JSON representation of the model.

        Returns:
            str: A JSON string representation of the model instance.
        """
        return json.dumps(self.to_dict(), default=str, indent=2)

    def __init__(self, **kwargs):
        """
        Initialise the model instance and cast attributes.

        Args:
            **kwargs: Key-value pairs of attributes to
            set on the model instance.
        """
        for key, value in kwargs.items():
            casted = self._cast(key, value)
            setattr(self, key, casted)

    def _cast(self, key, value):
        """
        Cast the value according to the model's `casts` configuration.

        Args:
            key (str): The attribute name.
            value (Any): The value to cast.

        Returns:
            Any: The casted value.
        """
        type_ = self.casts.get(key)
        if value is None:
            return value
        if type_ == "bool":
            return bool(value)
        elif type_ == "datetime":
            return datetime.fromisoformat(value)
        elif type_ == "json":
            return json.loads(value)
        return value

    @classmethod
    def is_fillable(cls, key):
        """
        Check if a key is mass-assignable.

        Args:
            key (str): The attribute name to check.

        Returns:
            bool: True if the key is fillable, False otherwise.
        """
        if cls.fillable:
            return key in cls.fillable
        return key not in cls.guarded

    @classmethod
    def validate(cls, data: dict):
        """
        Validate data before saving to the database (not implemented).

        Args:
            data (dict): The data to validate.

        Raises:
            NotImplementedError:
            Always raised since validation is not implemented.
        """
        raise NotImplementedError("Validation logic is not implemented")

    @classmethod
    def set_driver(cls, driver):
        """
        Set the driver used for executing queries.

        Args:
            driver: The database driver instance.
        """
        cls.driver = driver

    @classmethod
    async def find(cls, id):
        """
        Find a single row by primary key.

        Args:
            id (Any): The primary key value.

        Returns:
            Model: The model instance if found, or None.
        """
        query = f"SELECT * FROM {cls.table} WHERE id = ?"
        result = await cls.driver.fetch_one(query, [id])
        return cls(**result) if result else None

    @classmethod
    async def all(cls):
        """
        Return all rows from the table (excluding soft-deleted rows).

        Returns:
            list: A list of model instances.
        """
        query = f"SELECT * FROM {cls.table}"
        if cls.soft_deletes:
            query += " WHERE deleted_at IS NULL"
        results = await cls.driver.fetch_all(query, [])
        return [cls(**row) for row in results]

    @classmethod
    async def with_trashed(cls):
        """
        Return all rows including soft-deleted ones.

        Returns:
            list: A list of model instances.
        """
        query = f"SELECT * FROM {cls.table}"
        results = await cls.driver.fetch_all(query, [])
        return [cls(**row) for row in results]

    @classmethod
    async def where(cls, column, value):
        """
        Find rows by a specific column value.

        Args:
            column (str): The column name to filter by.
            value (Any): The value to match.

        Returns:
            list: A list of model instances matching the condition.
        """
        query = f"SELECT * FROM {cls.table} WHERE {column} = ?"
        if cls.soft_deletes:
            query += " AND deleted_at IS NULL"
        results = await cls.driver.fetch_all(query, [value])
        return [cls(**row) for row in results]

    @classmethod
    async def create(cls, **kwargs):
        """
        Insert a new row into the table and return the new instance.

        Args:
            **kwargs: Key-value pairs of attributes to set on the new row.

        Returns:
            Model: The newly created model instance,
            or None if creation failed.
        """
        # Filter attributes based on fillable fields
        filtered_kwargs = {
            k: v for k, v in kwargs.items() if cls.is_fillable(k)
        }
        keys = ', '.join(filtered_kwargs.keys())
        placeholders = ', '.join(['?'] * len(filtered_kwargs))
        values = list(filtered_kwargs.values())
        query = (
            f"INSERT INTO {cls.table} ({keys}) "
            f"VALUES ({placeholders}) RETURNING *"
        )
        result = await cls.driver.fetch_one(query, values)
        return cls(**result) if result else None

    @classmethod
    async def delete(cls, id):
        """
        Delete a row by ID (soft or hard depending on config).

        Args:
            id (Any): The primary key value of the row to delete.

        Returns:
            Any: The result of the delete operation.
        """
        if cls.soft_deletes:
            query = f"UPDATE {cls.table} \
                SET deleted_at = CURRENT_TIMESTAMP \
                    WHERE id = ?"
        else:
            query = f"DELETE FROM {cls.table} WHERE id = ?"
        return await cls.driver.execute(query, [id])

    async def update(self, **kwargs):
        """
        Update the current row's attributes in the database.

        Args:
            **kwargs: Key-value pairs of attributes to update.
        """
        # Filter attributes based on fillable fields
        filtered_kwargs = {
            k: v for k, v in kwargs.items() if self.is_fillable(k)
        }
        sets = ', '.join([f"{k} = ?" for k in filtered_kwargs])
        values = list(filtered_kwargs.values()) + [self.id]
        query = f"UPDATE {self.table} SET {sets} WHERE id = ?"
        await self.driver.execute(query, values)

    async def has_one(self, related_cls, foreign_key, local_key="id"):
        """
        Define a has-one relationship.

        Args:
            related_cls (Model): The related model class.
            foreign_key (str): The foreign key column in the related table.
            local_key (str, optional): The local key column. Defaults to "id".

        Returns:
            Model: The related model instance, or None if not found.
        """
        local_id = getattr(self, local_key)
        if local_id is None:
            return None
        query = f"SELECT * FROM {related_cls.table} \
            WHERE {foreign_key} = ? \
                LIMIT 1"
        result = await self.driver.fetch_one(query, [local_id])
        return related_cls(**result) if result else None

    async def has_many(self, related_cls, foreign_key, local_key="id"):
        """
        Define a has-many relationship.

        Args:
            related_cls (Model): The related model class.
            foreign_key (str): The foreign key column in the related table.
            local_key (str, optional): The local key column. Defaults to "id".

        Returns:
            list: A list of related model instances.
        """
        query = f"SELECT * FROM {related_cls.table} \
            WHERE {foreign_key} = ?"
        return await self._run_related_query(
            related_cls,
            query,
            [
                getattr(self, local_key)
            ]
        )

    async def belongs_to(self, related_cls, foreign_key, owner_key="id"):
        """
        Define a belongs-to relationship.

        Args:
            related_cls (Model): The related model class.
            foreign_key (str): The foreign key column in the current table.
            owner_key (str, optional): The primary key column in the related
            table. Defaults to "id".

        Returns:
            Model: The related model instance, or None if not found.
        """
        owner_id = getattr(self, foreign_key, None)
        if owner_id is None:
            return None
        query = (
            f"SELECT * FROM {related_cls.table} "
            f"WHERE {owner_key} = ?"
        )
        return await self._run_related_query(
            related_cls,
            query,
            [
                owner_id
            ],
            one=True
        )

    async def _run_related_query(self, related_cls, query, binds, one=False):
        """
        Helper method to execute relationship queries.

        Args:
            related_cls (Model): The related model class.
            query (str): The SQL query to execute.
            binds (list): The bind parameters for the query.
            one (bool, optional): Whether to fetch a single result.
            Defaults to False.

        Returns:
            Any: A single related model instance or
            a list of related model instances.
        """
        if one:
            result = await self.driver.fetch_one(query, binds)
            return related_cls(**result) if result else None
        results = await self.driver.fetch_all(query, binds)
        return [related_cls(**row) for row in results]

    @classmethod
    def query(cls):
        """
        Start a query builder for the model class.

        Returns:
            QueryBuilder: A new QueryBuilder instance for the model.
        """
        return QueryBuilder(cls, cls.driver)
