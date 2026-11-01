"""Fixtures of the recorder tests: a recorder whose database is ready before Home
Assistant loads the custom integration, and the SQL it runs kept out of the output."""

import logging
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    recorder_db_url: str, enable_custom_integrations: None
) -> None:
    """Let Home Assistant load integrations from custom_components/, after the
    recorder's database is ready: the recorder fixtures need that order, and the
    autouse fixture of the same name in tests/conftest.py would set Home Assistant up
    first."""


@pytest.fixture(autouse=True)
def quiet_sql_engine() -> Iterator[None]:
    """Keep the SQL the recorder runs out of the test output: the plugin sets
    `sqlalchemy.engine` to INFO for the whole session, and the recorder's thread
    prints each statement, some of them after the test is over. Set up before the
    recorder's fixtures, this one is also torn down after them."""
    engine = logging.getLogger("sqlalchemy.engine")
    level = engine.level
    engine.setLevel(logging.WARNING)
    yield
    engine.setLevel(level)
