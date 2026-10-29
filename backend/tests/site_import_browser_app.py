"""Local-only file adapter for isolated browser validation; not an Azure acceptance."""
from pathlib import Path
from hashlib import sha256
from sqlalchemy.engine import make_url
from dga.main import create_app
from dga.shared.config import Settings
from dga.shared.files import ObjectStorageError

settings=Settings()
url=make_url(settings.database_url.get_secret_value())
if (url.host,url.database,url.username)!=('db','dga_browser','dga_browser'):
    raise RuntimeError('Local browser fixture requires isolated database')

class LocalFiles:
    def __init__(self):
        self.root=Path(__file__).resolve().parents[2]/'.cache'/'browser-files'
        self.root.mkdir(parents=True,exist_ok=True)
    def path(self,key): return self.root/sha256(key.encode()).hexdigest()
    def put(self,*,object_key,content,content_type): self.path(object_key).write_bytes(content)
    def get(self,*,object_key):
        try: return self.path(object_key).read_bytes()
        except OSError as error: raise ObjectStorageError('local_test_file_missing') from error
    def delete(self,*,object_key): self.path(object_key).unlink(missing_ok=True)

app=create_app(settings,file_store=LocalFiles())
