# 🔥 CFlareModel

**CFlareModel** is a lightweight, async-first ORM for Python inspired by Laravel's Eloquent. Built with **Cloudflare D1** and **Cloudflare Workers** in mind, it offers a fluent API, relationship management, and automatic schema introspection — all in a minimal package.

> ⚠️ When using CFlareModel on Cloudflare Workers, you must vendor your Python dependencies. Follow this official guide:
> https://github.com/cloudflare/python-workers-examples/blob/main/06-vendoring/README.md

---

## ✨ Features

- ✅ Fluent, chainable query builder (`where()`, `with_()`, `limit()` etc.)
- ⚡ Async by default — built for modern Python 3.8+
- 🔁 Eager and lazy loading of relationships
- ☁️ D1-first, but pluggable with other SQL drivers

---

## 📦 Installation

```bash
pip install cflaremodel
```

---

## 🚀 Quickstart

```python
from cflaremodel import Model
from cflaremodel import D1Driver

# Example User model
class User(Model):
    table = "users"
    fillable = ["name", "email"]
    casts = {"created_at": "datetime"}

async def on_fetch(request, env):
    # Setup driver
    Model.set_driver(driver=D1Driver(env.DB))
    # Query
    users = await User.query().where("email", "like", "%@example.com").get()
```

---

## 🧱 Defining Relationships

```python
class Post(Model):
    table = "posts"

    async def user(self):
        return await self.belongs_to(User, "user_id")

class User(Model):
    table = "users"

    async def posts(self):
        return await self.has_many(Post, "user_id")
```
---

## 📜 License

GNU GPLv3 © 2025 — avltree9798