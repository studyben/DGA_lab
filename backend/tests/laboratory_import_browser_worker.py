"""Local-only worker counterpart to the owned native browser file fixture."""
import logging
import time
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.engine import make_url
from dga.shared.config import Settings
from dga.laboratory.import_worker import build_service
from tests.laboratory_import_browser_app import LocalFiles

def main():
    settings=Settings()
    url=make_url(settings.database_url.get_secret_value())
    if (url.host,url.database,url.username)!=('db','dga_browser','dga_browser'):
        raise RuntimeError('Requires isolated browser namespace')
    service,engine=build_service(settings,file_store=LocalFiles())
    with engine.connect() as c:
        if tuple(c.execute(text("SELECT current_database(),current_user,current_schema()")).one())!=('dga_browser','dga_browser','public'):
            raise RuntimeError('Unexpected browser database namespace')
    worker='native-lab-'+uuid4().hex
    try:
        while True:
            try: processed=service.process_next(worker)
            except Exception as error:
                logging.warning('Owned browser validation worker retry (%s)',type(error).__name__)
                processed=False
            if not processed: time.sleep(0.25)
    finally: engine.dispose()

if __name__=='__main__': main()

