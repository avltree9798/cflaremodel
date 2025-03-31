import pytest

from cflaremodel.model import Model


class MockDriver:
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


class User(Model):
    table = "users"
    fillable = ["id", "name", "email"]
    casts = {"id": "int"}


@pytest.fixture
def mock_driver():
    driver = MockDriver()
    User.set_driver(driver)
    return driver


@pytest.mark.asyncio
async def test_model_find(mock_driver):
    user = await User.find(1)
    assert user.id == 1
    assert user.name == "Test"
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
    assert mock_driver.last_params[0] == "%@example.com"


@pytest.mark.asyncio
async def test_query_builder_limit_offset(mock_driver):
    users = await User.query().limit(1).offset(1).get()
    assert len(users) == 2
    assert "LIMIT 1" in mock_driver.last_query
    assert "OFFSET 1" in mock_driver.last_query


@pytest.mark.asyncio
async def test_query_builder_select_group_by(mock_driver):
    _ = await User.query().select("id", "email").group_by("email").get()
    assert "SELECT id, email" in mock_driver.last_query
    assert "GROUP BY email" in mock_driver.last_query
