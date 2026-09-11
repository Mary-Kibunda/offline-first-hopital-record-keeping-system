"""Alembic migration environment.

The database URL is taken from the application settings rather than duplicated
here, so ``.env`` remains the single source of truth. Run alembic from the
project root so that ``alembic.ini`` and the ``.env`` file are both found.

The model modules are imported for their side effect: a SQLAlchemy model is
only registered on ``Base.metadata`` once its module has been imported, and
autogenerate can only diff tables it can see there. When you add a new model
module under ``app/models/``, add it to the imports inside :func:`import_models`
below or autogenerate will silently emit an empty migration.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def import_models() -> None:
    """Import every model module so ``Base.metadata`` is fully populated."""
    from app.models import enums  # noqa: F401
    from app.models import user  # noqa: F401

    # The modules below currently exist as empty placeholders. Uncomment each
    # one as its classes are written; autogenerate will then pick the tables up
    # automatically:
    #
    # from app.models import appointment, consultation, drug_stock, hospital
    # from app.models import patient, perscription, sync_log


import_models()

target_metadata = Base.metadata

DATABASE_URL = str(settings.DATABASE_URL)

# ``set_main_option`` writes through configparser, which treats ``%`` as an
# interpolation marker. Passwords routinely contain URL-encoded characters
# such as ``%3F`` (``?``), so the percent signs must be doubled on the way in;
# configparser collapses them back to single ``%`` when the value is read out
# again, so the URL that reaches the engine is the original string.
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))


def run_migrations_offline() -> None:
    """Run migrations without a live connection, emitting SQL to stdout.

    Invoked with ``alembic upgrade head --sql``. Useful for reviewing what a
    migration would do, or handing the statements to a DBA.
    """
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        # Offline mode renders straight from the raw URL, so no escaping is
        # needed here.
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Surface column type and server default changes in autogenerate,
            # instead of only detecting added and removed tables and columns.
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
