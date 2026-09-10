from contextlib import asynccontextmanager
from pathlib import Path
from secrets import compare_digest

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from dga.shared.config import Settings
from dga.assets.public import (
    MODULE as ASSETS,
    AssetDirectory,
    AssetQueryError,
    access_context as asset_access,
    http_router as assets_router,
)
from dga.laboratory.public import (
    MODULE as LABORATORY,
    LaboratoryError,
    SampleRegistry,
    access_context as laboratory_access,
    http_router as laboratory_router,
)
from dga.condition_analysis.public import MODULE as CONDITION_ANALYSIS, access_context as analysis_access
from dga.shared.contracts import ModuleDescriptor
from dga.shared.auth.public import AuditTrail, IdentityService, IdentityError
from dga.shared.auth.http import auth_router, COOKIE


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

    @app.exception_handler(AssetQueryError)
    async def asset_query_error(request, error):
        return JSONResponse(
            status_code=error.status,
            content={'code': error.code},
            headers={'Cache-Control': 'no-store'},
        )

    @app.exception_handler(LaboratoryError)
    async def laboratory_error(request, error):
        return JSONResponse(
            status_code=error.status,
            content={'code': error.code},
            headers={'Cache-Control': 'no-store'},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # Pydantic error input/context can contain plaintext credentials.
        return JSONResponse(status_code=422, content={'code': 'invalid_input'})

    @app.get('/api/modules')
    def modules(request: Request) -> list[ModuleDescriptor]:
        actor = current_actor(request)
        return [module for module, permission in [(ASSETS, 'assets.read'), (LABORATORY, 'laboratory.read'), (CONDITION_ANALYSIS, 'analysis.read')]
                if permission in actor.permissions]

    def current_actor(request: Request):
        actor = identity.session(request.cookies.get(COOKIE, '')).actor
        if actor.must_change_password:
            raise IdentityError('password_change_required', 403)
        return actor

    def mutation_actor(request: Request):
        if request.headers.get('origin') not in set(settings.auth_allowed_origins.split(',')):
            raise IdentityError('origin_rejected', 403)
        session = identity.session(request.cookies.get(COOKIE, ''))
        supplied = request.headers.get('x-csrf-token', '').encode('utf-8')
        if not compare_digest(supplied, session.csrf_token.encode('utf-8')):
            raise IdentityError('csrf_rejected', 403)
        if session.actor.must_change_password:
            raise IdentityError('password_change_required', 403)
        return session.actor

    asset_directory = AssetDirectory(engine)
    app.include_router(assets_router(asset_directory, current_actor))
    app.include_router(
        laboratory_router(
            SampleRegistry(engine, asset_directory, AuditTrail()),
            current_actor,
            mutation_actor,
        )
    )

    @app.get('/api/assets/access')
    def assets_context(actor=Depends(current_actor)):
        return asset_access(actor)

    @app.get('/api/laboratory/access')
    def lab_context(actor=Depends(current_actor)):
        return laboratory_access(actor)

    @app.get('/api/condition-analysis/access')
    def condition_context(actor=Depends(current_actor)):
        return analysis_access(actor)

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
