import os

import pytest

from app.postgres.database import (
    init_postgres_database,
    postgres_schema_version,
)
from app.postgres.migrations import POSTGRES_SCHEMA_VERSION


DATABASE_URL = os.getenv("TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TEST_POSTGRES_URL is not configured",
)


def test_postgres_migrations_reach_current_version_idempotently() -> None:
    init_postgres_database(str(DATABASE_URL))
    init_postgres_database(str(DATABASE_URL))

    assert postgres_schema_version(str(DATABASE_URL)) == (
        POSTGRES_SCHEMA_VERSION
    )
