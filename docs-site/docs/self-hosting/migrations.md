---
sidebar_label: Migrations
---

# Migrations

The database schema is managed with Alembic. Migrations live in `alembic/versions/`, configured by `alembic.ini` (`script_location = %(here)s/alembic`).

## Applying migrations

```bash
alembic upgrade head
```

In the Docker stack this runs automatically: the one-shot `migrate` service (`docker-compose.yml`) executes `alembic upgrade head` against the `db` service after it reports healthy, then exits. See [Docker Compose](./docker-compose.md).

For a local backend, run the same command after activating your environment.

## Single head

The migration graph has a single head. The current head is `e7d202b2a325` (`e7d202b2a325_drop_billing_tables.py`). A single head means `alembic upgrade head` is unambiguous and the deploy never has to pick between divergent branches.

There is a merge revision in the history (`656dca26764a`, with a tuple `down_revision`) that joins two earlier branches; that is expected and does not create a second head.

## Checking state

```bash
alembic current       # revision currently applied to the database
alembic heads         # should print exactly one head
alembic history       # full revision graph
```

> The `alembic_version` table records intent, not reality. If tables were dropped or altered outside Alembic, verify the actual schema (e.g. `\dt` in psql) before assuming a migration applied cleanly.

## Connection

`alembic.ini` ships a development `sqlalchemy.url` (`postgresql+asyncpg://fishcloud:fishcloud@localhost:5432/fishcloud`). The `migrate` service overrides the connection at runtime via the `DATABASE_URL` it receives from Compose, pointing at the `db` container.
