"""Owned laboratory import browser fixture; local bytes are not a hosted provider claim."""
from hashlib import sha256
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from dga.main import create_app
from dga.shared.config import Settings
from dga.shared.files import ObjectStorageError

settings = Settings()
url = make_url(settings.database_url.get_secret_value())
if (url.host, url.database, url.username) != ('db', 'dga_browser', 'dga_browser'):
    raise RuntimeError('Requires an isolated browser database')
with create_engine(url).connect() as connection:
    actual = connection.execute(text("SELECT current_database(),current_user,current_schema()")).one()
    if tuple(actual) != ('dga_browser', 'dga_browser', 'public'):
        raise RuntimeError('Unexpected browser database namespace')


class LocalFiles:
    def __init__(self):
        self.root = Path(__file__).resolve().parents[2]/'.cache'/'issue52-browser-files'
        self.root.mkdir(parents=True, exist_ok=True)
    def path(self, key):
        return self.root/sha256(key.encode()).hexdigest()
    def put(self, *, object_key, content, content_type):
        self.path(object_key).write_bytes(content)
    def get(self, *, object_key):
        try:
            return self.path(object_key).read_bytes()
        except OSError as error:
            raise ObjectStorageError('local_browser_original_unavailable') from error
    def delete(self, *, object_key):
        self.path(object_key).unlink(missing_ok=True)


app = create_app(settings, file_store=LocalFiles())

