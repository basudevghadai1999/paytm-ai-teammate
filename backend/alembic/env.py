from alembic import context
from sqlalchemy import create_engine

from app.core.config import settings

url = settings.migration_database_url or settings.database_url

# Own version table: never collides with COOLops' alembic_version in the shared database.
VERSION_TABLE = "alembic_version_teammate"


def run() -> None:
    engine = create_engine(url)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=None, version_table=VERSION_TABLE)
        with context.begin_transaction():
            context.run_migrations()


run()
