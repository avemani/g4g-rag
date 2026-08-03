import asyncio
from pipeline.core.data_migration import DataMigrator


if __name__ == '__main__':
    migrator = DataMigrator()
    asyncio.run(migrator.migrate_data(truncate=True))