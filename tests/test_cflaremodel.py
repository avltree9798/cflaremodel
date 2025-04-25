import pytest

from cflaremodel import Driver, Model


class MockDriver(Driver):
    def __init__(self):
        self.last_query = None
        self.last_params = None

    async def fetch_one(self, query, params):
        self.last_query = query
        self.last_params = params
        return {"id": 1, "name": "Test", "email": "test@example.com"}

    async def fetch_all(self, query, params):
        self.last_query = query
        self.last_params = params
        return [
            {"id": 1, "name": "Test", "email": "test@example.com"},
            {"id": 2, "name": "Another", "email": "another@example.com"}
        ]

    async def execute(self, query, params):
        self.last_query = query
        self.last_params = params
        return True


class Post(Model):
    table = "posts"
    fillable = ["id", "user_id", "title"]


class User(Model):
    table = "users"
    fillable = ["id", "name", "email"]
    casts = {"id": "int"}

    async def posts(self):
        return [Post(id=1, user_id=self.id, title="First")]


@pytest.fixture
def mock_driver():
    driver = MockDriver()
    User.set_driver(driver)
    return driver


@pytest.mark.asyncio
async def test_model_find(mock_driver):
    user = await User.find(1)
    assert user.id == 1
    assert mock_driver.last_query.startswith("SELECT")


@pytest.mark.asyncio
async def test_model_create(mock_driver):
    user = await User.create(name="Test", email="test@example.com")
    assert user.name == "Test"
    assert "INSERT INTO" in mock_driver.last_query


@pytest.mark.asyncio
async def test_model_update(mock_driver):
    user = User(id=1, name="Old", email="old@example.com")
    await user.update(name="New")
    assert "UPDATE" in mock_driver.last_query
    assert mock_driver.last_params[0] == "New"


@pytest.mark.asyncio
async def test_query_builder_where(mock_driver):
    users = await User.query().where("email", "like", "%@example.com").get()
    assert len(users) == 2
    assert "WHERE email like ?" in mock_driver.last_query


@pytest.mark.asyncio
async def test_query_builder_limit_offset(mock_driver):
    await User.query().limit(1).offset(1).get()
    assert "LIMIT 1" in mock_driver.last_query
    assert "OFFSET 1" in mock_driver.last_query


@pytest.mark.asyncio
async def test_query_builder_select_group_by(mock_driver):
    await User.query().select("id", "email").group_by("email").get()
    assert "SELECT id, email" in mock_driver.last_query
    assert "GROUP BY email" in mock_driver.last_query


@pytest.mark.asyncio
async def test_query_builder_order_by(mock_driver):
    await User.query().order_by("name", "DESC").get()
    assert "ORDER BY name DESC" in mock_driver.last_query


@pytest.mark.asyncio
async def test_query_builder_joins(mock_driver):
    await User.query().join(
        "profiles",
        "users.id",
        "profiles.user_id"
    ).get()
    query = "JOIN profiles ON users.id = profiles.user_id"
    assert query in mock_driver.last_query

    await User.query().left_join(
        "profiles",
        "users.id",
        "profiles.user_id"
    ).get()
    query = "LEFT JOIN profiles ON users.id = profiles.user_id"
    assert query in mock_driver.last_query

    await User.query().right_join(
        "profiles",
        "users.id",
        "profiles.user_id"
    ).get()
    query = "RIGHT JOIN profiles ON users.id = profiles.user_id"
    assert query in mock_driver.last_query

    await User.query().cross_join("countries").get()
    assert "CROSS JOIN countries" in mock_driver.last_query


@pytest.mark.asyncio
async def test_query_builder_union(mock_driver):
    q1 = User.query().where("email", "like", "%@example.com")
    q2 = User.query().where("email", "like", "%@test.com")
    q1.union(q2)
    await q1.get()
    assert "UNION" in mock_driver.last_query


@pytest.mark.asyncio
async def test_query_builder_first(mock_driver):
    user = await User.query().where("name", "Test").first()
    assert isinstance(user, User)
    assert "LIMIT 1" in mock_driver.last_query


@pytest.mark.asyncio
async def test_query_builder_with_eager_loading(mock_driver, monkeypatch):
    async def mock_posts(self):
        return [Post(id=1, user_id=self.id, title="First")]

    setattr(User, "posts", mock_posts)

    # Patch the driver's fetch_all to return Post rows when eager loading
    async def mock_fetch_all(query, params):
        if "FROM posts" in query:
            return [
                {"id": 1, "user_id": 1, "title": "First"},
                {"id": 2, "user_id": 2, "title": "Second"}
            ]
        return [
            {"id": 1, "name": "Test", "email": "test@example.com"},
            {"id": 2, "name": "Another", "email": "another@example.com"}
        ]

    monkeypatch.setattr(mock_driver, "fetch_all", mock_fetch_all)
    users = await User.query().with_("posts").get()
    assert hasattr(users[0], "posts")
    assert isinstance(users[0].posts, list)
    assert users[0].posts[0].title == "First"


@pytest.mark.asyncio
async def test_model_save(mock_driver):
    # Create a user instance with initial data
    user = User(id=1, name="Old Name", email="old@example.com")

    # Modify the user's attributes
    user.name = "New Name"
    user.email = "new@example.com"

    # Call the save method to persist changes
    result = await user.save()

    # Assert that the save method detected changes and updated the database
    assert result is True
    query = "UPDATE users SET name = ?, email = ? WHERE id = ?"
    assert query in mock_driver.last_query
    assert mock_driver.last_params == ["New Name", "new@example.com", 1]

    # Call save again without making any changes
    result = await user.save()

    # Assert that no changes were detected and no update query was executed
    assert result is False
