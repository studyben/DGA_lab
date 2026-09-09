from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from dga.shared.config import Settings
from dga.assets.public import MODULE as ASSETS
from dga.laboratory.public import MODULE as LABORATORY
from dga.condition_analysis.public import MODULE as CONDITION_ANALYSIS
from dga.shared.contracts import ModuleDescriptor
from dga.shared.auth.public import IdentityService, IdentityError
from dga.shared.auth.http import auth_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    migrations = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    expected_heads = set(ScriptDirectory.from_config(migrations).get_heads())
    engine = create_engine(
        settings.database_url.get_secret_value(),
        connect_args={'connect_timeout': 3, 'options': '-c statement_timeout=3000'},
        pool_pre_ping=True,
        pool_timeout=3,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title='DGA Lab', lifespan=lifespan)
    identity = IdentityService(engine, session_hours=settings.session_hours)
    app.include_router(auth_router(identity, settings))

    @app.exception_handler(IdentityError)
    async def identity_error(request, error):
        return JSONResponse(status_code=error.status, content={'code': error.code}, headers={'Cache-Control': 'no-store'})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # Pydantic error input/context can contain plaintext credentials.
        return JSONResponse(status_code=422, content={'code': 'invalid_input'})

    @app.get('/api/modules')
    def modules() -> list[ModuleDescriptor]:
        return [ASSETS, LABORATORY, CONDITION_ANALYSIS]

    @app.get('/api/health')
    def health():
        try:
            with engine.connect() as connection:
                connection.execute(text('SELECT 1'))
                if set(MigrationContext.configure(connection).get_current_heads()) != expected_heads:
                    return JSONResponse(status_code=503, content={'status': 'unavailable', 'database': 'unavailable'})
        except SQLAlchemyError:
            return JSONResponse(status_code=503, content={'status': 'unavailable', 'database': 'unavailable'})
        return {'status': 'ok', 'database': 'ok'}

    return app
