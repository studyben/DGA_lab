"""Bounded single-job laboratory validation runner using the API's configured store."""
import argparse
import logging
import time
from uuid import uuid4
from sqlalchemy import create_engine
from dga.assets.public import AssetDirectory
from dga.shared.auth.public import AuditTrail,IdentityService
from dga.shared.config import Settings
from dga.shared.file_store_factory import create_file_store
from dga.shared.files import UnavailableFileStore
from .configuration import LaboratoryConfiguration
from .imports import LaboratoryImports

logger=logging.getLogger(__name__)


def build_service(settings,*,file_store=None):
    store=file_store if file_store is not None else create_file_store(settings)
    if isinstance(store,UnavailableFileStore): raise RuntimeError('object_storage_not_configured')
    engine=create_engine(settings.database_url.get_secret_value(),
        connect_args={'connect_timeout':3,'options':'-c statement_timeout=30000'},pool_pre_ping=True,pool_timeout=3)
    return LaboratoryImports(engine,store,identities=IdentityService(engine),audit=AuditTrail(),
        assets=AssetDirectory(engine),configuration=LaboratoryConfiguration(engine)),engine


def main():
    parser=argparse.ArgumentParser(description='Validate staged laboratory originals; never formal publication.')
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    service,engine=build_service(Settings())
    worker_id='laboratory-'+uuid4().hex
    try:
        while True:
            try: processed=service.process_next(worker_id)
            except Exception as error:
                # Preserve lease/unknown-COMMIT state; no source values or provider secrets.
                logger.warning('Laboratory validation iteration unavailable (%s)',type(error).__name__)
                if args.once: raise
                processed=False
            if args.once: return
            if not processed: time.sleep(0.5)
    finally: engine.dispose()


if __name__=='__main__': main()

