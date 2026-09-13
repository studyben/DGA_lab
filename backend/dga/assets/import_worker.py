"""Run only durable staged-import validation; no generic task framework."""
import argparse
import logging
import time
from sqlalchemy import create_engine
from dga.shared.config import Settings
from dga.shared.files import UnavailableFileStore
from .public import AssetImports


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    settings = Settings()
    engine = create_engine(settings.database_url.get_secret_value(), pool_pre_ping=True,
                           connect_args={'connect_timeout': 3, 'options': '-c statement_timeout=30000'})
    imports = AssetImports(engine, UnavailableFileStore())
    try:
        while True:
            try:
                processed = imports.validate_next()
            except Exception:
                logging.error('Import validator unavailable; pending batches remain retryable.')
                if args.once:
                    raise
                processed = False
            if args.once:
                return
            if not processed:
                time.sleep(2)
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
