"""Explicit fake catalog for isolated browser tests, never an acceptance-data seed."""
from sqlalchemy import create_engine, text
from dga.shared.config import Settings

if __name__ == '__main__':
    url = Settings().database_url.get_secret_value()
    if '@db:5432/dga_browser' not in url:
        raise RuntimeError('Requires isolated dga_browser database')
    engine = create_engine(url)
    with engine.begin() as c:
        c.execute(text("INSERT INTO asset_materials VALUES ('MAT-TX-41','TX-4400','TRANSFORMER') ON CONFLICT DO NOTHING"))
    engine.dispose()
