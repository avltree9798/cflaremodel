
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
        return iter(self.to_dict().items())

    def to_dict(self):
        """
        Serialise the model instance to a dictionary excluding hidden fields.
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
        """Return a pretty-printed JSON representation of the model."""
        return json.dumps(self.to_dict(), default=str, indent=2)

    def __init__(self, **kwargs):
        """Initialise the model instance and cast attributes."""
        for key, value in kwargs.items():
            if self.is_fillable(key):
                casted = self._cast(key, value)
                setattr(self, key, casted)

    def _cast(self, key, value):
        """Cast the value according to the model's `casts` configuration."""
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
        """Check if a key is mass-assignable."""
        if cls.fillable:
            return key in cls.fillable
        return key not in cls.guarded

    @classmethod
    def validate(cls, data: dict):
        """Validate data before saving to database (not implemented)."""
        raise NotImplementedError("Validation logic is not implemented")

    @classmethod
    def set_driver(cls, driver):
        """Set the driver used for executing queries."""
        cls.driver = driver

    @classmethod
    async def find(cls, id):
        """Find a single row by primary key."""
        query = f"SELECT * FROM {cls.table} WHERE id = ?"
        result = await cls.driver.fetch_one(query, [id])
        return cls(**result) if result else None

    @classmethod
    async def all(cls):
        """Return all rows from the table (excluding soft-deleted)."""
        query = f"SELECT * FROM {cls.table}"
        if cls.soft_deletes:
            query += " WHERE deleted_at IS NULL"
        results = await cls.driver.fetch_all(query, [])
        return [cls(**row) for row in results]

    @classmethod
    async def with_trashed(cls):
        """Return all rows including soft-deleted ones."""
        query = f"SELECT * FROM {cls.table}"
        results = await cls.driver.fetch_all(query, [])
        return [cls(**row) for row in results]

    @classmethod
    async def where(cls, column, value):
        """Find rows by a specific column value."""
        query = f"SELECT * FROM {cls.table} WHERE {column} = ?"
        if cls.soft_deletes:
            query += " AND deleted_at IS NULL"
        results = await cls.driver.fetch_all(query, [value])
        return [cls(**row) for row in results]

    @classmethod
    async def create(cls, **kwargs):
        """Insert a new row into the table and return the new instance."""
        keys = ', '.join(kwargs.keys())
        placeholders = ', '.join(['?'] * len(kwargs))
        values = list(kwargs.values())
        query = f"INSERT INTO \
            {cls.table} ({keys}) \
                VALUES ({placeholders}) RETURNING *"
        result = await cls.driver.fetch_one(query, values)
        return cls(**result) if result else None

    @classmethod
    async def delete(cls, id):
        """Delete a row by ID (soft or hard depending on config)."""
        if cls.soft_deletes:
            query = f"UPDATE {cls.table} \
                SET deleted_at = CURRENT_TIMESTAMP \
                    WHERE id = ?"
        else:
            query = f"DELETE FROM {cls.table} WHERE id = ?"
        return await cls.driver.execute(query, [id])

    async def update(self, **kwargs):
        """Update current row's attributes in the database."""
        sets = ', '.join([f"{k} = ?" for k in kwargs])
        values = list(kwargs.values()) + [self.id]
        query = f"UPDATE {self.table} SET {sets} WHERE id = ?"
        await self.driver.execute(query, values)

    async def has_one(self, related_cls, foreign_key, local_key="id"):
        """Define a has-one relationship."""
        local_id = getattr(self, local_key)
        query = f"SELECT * FROM {related_cls.table} \
            WHERE {foreign_key} = ? \
                LIMIT 1"
        result = await self.driver.fetch_one(query, [local_id])
        return related_cls(**result) if result else None

    async def has_many(self, related_cls, foreign_key, local_key="id"):
        """Define a has-many relationship."""
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
        """Define a belongs-to relationship."""
        owner_id = getattr(self, foreign_key)
        query = f"SELECT * FROM {related_cls.table} WHERE {owner_key} = ?"
        return await self._run_related_query(
            related_cls,
            query,
            [
                owner_id
            ],
            one=True
        )

    async def _run_related_query(self, related_cls, query, binds, one=False):
        """Helper method to execute relationship queries."""
        if one:
            result = await self.driver.fetch_one(query, binds)
            return related_cls(**result) if result else None
        results = await self.driver.fetch_all(query, binds)
        return [related_cls(**row) for row in results]

    @classmethod
    def query(cls):
        """Start a query builder for the model class."""
        return QueryBuilder(cls, cls.driver)
