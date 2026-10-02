from contextlib import asynccontextmanager
from pathlib import Path

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
    AssetLifecycle,
    AssetImports,
    import_http_router,
    AssetQueryError,
    access_context as asset_access,
    http_router as assets_router,
)
from dga.laboratory.public import (
    MODULE as LABORATORY,
    LaboratoryError,
    LaboratoryWorkbench,
    LaboratoryReports,
    LaboratoryOperations,
    LaboratoryConfiguration,
    LaboratoryTrendSource,
    configuration_router,
    operations_router,
    SampleRegistry,
    access_context as laboratory_access,
    http_router as laboratory_router,
)
from dga.condition_analysis.public import (
    MODULE as CONDITION_ANALYSIS, access_context as analysis_access,
    TransformerTrends, http_router as analysis_router,
    HealthRules, DeviceHealth, HealthError, health_router,
    AlarmCenter, alarm_router,
)
from dga.shared.contracts import ModuleDescriptor
from dga.shared.auth.public import AuditTrail, IdentityService, IdentityError
from dga.shared.auth.http import AuthenticatedRequests, auth_router
from dga.shared.files import FileStore, ObjectStorageError, S3CompatibleFileStore, UnavailableFileStore


def create_app(settings: Settings | None = None, *, file_store: FileStore | None = None) -> FastAPI:
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
    requests = AuthenticatedRequests(identity, settings)
    app.include_router(auth_router(identity, settings, requests))

    @app.exception_handler(IdentityError)
    async def identity_error(request, error):
        return JSONResponse(status_code=error.status, content={'code': error.code}, headers={'Cache-Control': 'no-store'})

    @app.exception_handler(HealthError)
    async def health_error(request,error):
        return JSONResponse(status_code=error.status,content={'code':error.code},headers={'Cache-Control':'no-store'})

    @app.exception_handler(AssetQueryError)
    async def asset_query_error(request, error):
        return JSONResponse(
            status_code=error.status,
            content={'code': error.code},
            headers={'Cache-Control': 'no-store'},
        )

    @app.exception_handler(LaboratoryError)
    async def laboratory_error(request, error):
        content = {'code': error.code}
        if error.details is not None:
            content['details'] = error.details
        return JSONResponse(
            status_code=error.status,
            content=content,
            headers={'Cache-Control': 'no-store'},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # Pydantic error input/context can contain plaintext credentials.
        return JSONResponse(status_code=422, content={'code': 'invalid_input'}, headers={'Cache-Control': 'no-store'})

    @app.get('/api/modules')
    def modules(request: Request) -> list[ModuleDescriptor]:
        actor = current_actor(request)
        return [module for module, permission in [(ASSETS, 'assets.read'), (LABORATORY, 'laboratory.read'), (CONDITION_ANALYSIS, 'analysis.read')]
                if permission in actor.permissions]

    current_actor = requests.actor
    mutation_actor = requests.mutation_actor

    asset_directory = AssetDirectory(engine)
    health_rules=HealthRules(engine,LaboratoryConfiguration(engine),asset_directory)
    app.include_router(alarm_router(AlarmCenter(engine,asset_directory,LaboratoryTrendSource(engine)),current_actor,mutation_actor))
    app.include_router(health_router(health_rules,DeviceHealth(engine,asset_directory,LaboratoryTrendSource(engine),health_rules),current_actor,mutation_actor))
    app.include_router(analysis_router(TransformerTrends(asset_directory, LaboratoryTrendSource(engine)), current_actor))
    app.include_router(assets_router(asset_directory, current_actor, AssetLifecycle(engine), mutation_actor))
    configured_object_store = file_store if file_store is not None else UnavailableFileStore()
    if file_store is None and all((settings.object_store_endpoint, settings.object_store_bucket,
            settings.object_store_access_key, settings.object_store_secret_key)):
        configured_object_store = S3CompatibleFileStore(
            settings.object_store_endpoint,
            settings.object_store_bucket,
            settings.object_store_access_key.get_secret_value(),
            settings.object_store_secret_key.get_secret_value(),
            region=settings.object_store_region,
        )
    app.include_router(import_http_router(AssetImports(engine, configured_object_store), current_actor, mutation_actor))

    @app.exception_handler(ObjectStorageError)
    async def object_storage_error(request, error):
        return JSONResponse(
            status_code=503,
            content={'code': 'object_storage_unavailable'},
            headers={'Cache-Control': 'no-store'},
        )
    sample_registry = SampleRegistry(engine, asset_directory, AuditTrail())
    app.include_router(configuration_router(LaboratoryConfiguration(engine), current_actor, mutation_actor))
    app.include_router(operations_router(
        LaboratoryOperations(engine, sample_registry, asset_directory, AuditTrail()), current_actor, mutation_actor,
    ))
    audit_trail = AuditTrail()
    reports = LaboratoryReports(engine, audit_trail, configured_object_store)
    app.include_router(
        laboratory_router(
            sample_registry,
            LaboratoryWorkbench(
                engine, sample_registry, audit_trail, configured_object_store, reports
            ),
            reports,
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
