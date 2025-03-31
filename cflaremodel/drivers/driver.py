class Driver:
    """
    Abstract base class for a database driver.
    All database drivers must implement this interface.
    """

    async def fetch_one(self, query, params):
        """
        Execute a SQL query and return a single row.

        Args:
            query (str): The SQL query to execute.
            params (list): The list of parameters to bind to the query.

        Returns:
            dict: A single row as a dictionary, or None if no result found.
        """
        raise NotImplementedError()

    async def fetch_all(self, query, params):
        """
        Execute a SQL query and return all matching rows.

        Args:
            query (str): The SQL query to execute.
            params (list): The list of parameters to bind to the query.

        Returns:
            list[dict]: A list of rows, each represented as a dictionary.
        """
        raise NotImplementedError()

    async def execute(self, query, params):
        """
        Execute a SQL query that does not return any rows
        (e.g., INSERT, UPDATE, DELETE).

        Args:
            query (str): The SQL query to execute.
            params (list): The list of parameters to bind to the query.

        Returns:
            Any: The result of the execution,
            depending on the driver implementation.
        """
        raise NotImplementedError()
