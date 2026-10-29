"""OIDC transport: fixed redirects, browser binding, administrator Origin/CSRF guards."""
import logging
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from .http import COOKIE
from .oidc import CandidateInput
from .public import IdentityError

BINDING = 'dga_oidc_flow'


class OidcAccessLogFilter(logging.Filter):
    def filter(self, record):
        # Uvicorn access args: client, method, full_path, HTTP version, status.
        if isinstance(record.args, tuple) and len(record.args) == 5:
            client, method, path, version, status = record.args
            if isinstance(path, str) and path.split('?', 1)[0].startswith('/api/auth/oidc/'):
                record.args = (client, method, '/api/auth/oidc/callback', version, status)
        return True


class ActivateInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    config_id: UUID
    proof_id: UUID
    expected_revision: StrictInt = Field(ge=0)


class BindInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    user_id: UUID
    proof_id: UUID
    expected_revision: StrictInt = Field(ge=0)


def oidc_router(service, requests, settings):
    access_logger = logging.getLogger('uvicorn.access')
    if not any(isinstance(f, OidcAccessLogFilter) for f in access_logger.filters):
        access_logger.addFilter(OidcAccessLogFilter())

    def no_store(response: Response):
        response.headers['Cache-Control'] = 'no-store'

    router = APIRouter(prefix='/api/auth/oidc', dependencies=[Depends(no_store)])

    @router.get('/available')
    def available():
        return service.availability()

    @router.get('/configuration')
    def configuration(actor=Depends(requests.actor)):
        return service.configuration(actor)

    @router.post('/candidates', status_code=201)
    def candidate(body: CandidateInput, actor=Depends(requests.mutation_actor)):
        return {'id': service.save_candidate(actor, **body.model_dump())}

    def begin(flow):
        response = Response(content=None, status_code=200, headers={'Cache-Control': 'no-store'})
        response.set_cookie(BINDING, flow['browser_binding'], httponly=True, secure=settings.cookie_secure,
            samesite='lax', path='/api/auth/oidc', max_age=600)
        # JSON URL lets the UI show errors before navigating, not an AJAX-only redirect.
        from fastapi.responses import JSONResponse
        body = JSONResponse({'authorization_url': flow['authorization_url']}, headers={'Cache-Control': 'no-store'})
        body.headers.append('set-cookie', response.headers['set-cookie'])
        return body

    @router.post('/start')
    def start(request: Request):
        requests.require_origin(request)
        return begin(service.start_login(origin=request.headers.get('origin')))

    @router.post('/candidates/{config_id}/test')
    def test(config_id: UUID, request: Request):
        requests.csrf_session(request)
        return begin(service.start_test(request.cookies.get(COOKIE, ''), config_id, origin=request.headers.get('origin')))

    @router.post('/activate')
    def activate(body: ActivateInput, actor=Depends(requests.mutation_actor)):
        service.activate(actor, **body.model_dump())
        return {'updated': True}

    @router.post('/bind')
    def bind(body: BindInput, actor=Depends(requests.mutation_actor)):
        service.bind_identity(actor, **body.model_dump())
        return {'updated': True}

    @router.get('/callback')
    def callback(request: Request):
        session = None
        try:
            # Duplicate or provider error parameters cannot silently select a different flow/code.
            params = request.query_params
            if any(len(params.getlist(key)) != 1 for key in ('state',)) or len(params.getlist('code')) > 1:
                raise IdentityError('oidc_flow_invalid', 400)
            result = service.callback(params.get('state', ''), request.cookies.get(BINDING, ''),
                '' if 'error' in params else params.get('code', ''), request.cookies.get(COOKIE, ''))
            if result['purpose'] == 'LOGIN':
                session, target = result['session'], '/assets'
            else:
                target = '/settings/sso?oidc=tested'
        except IdentityError as error:
            # Never propagate provider error_description, code, state, token or secret in redirects.
            target = '/login?' + urlencode({'oidc_error': error.code})
        response = RedirectResponse(target, status_code=303,
            headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})
        response.delete_cookie(BINDING, path='/api/auth/oidc', secure=settings.cookie_secure, httponly=True, samesite='lax')
        if session:
            response.set_cookie(COOKIE, session.token, httponly=True, secure=settings.cookie_secure,
                samesite='lax', path='/', max_age=8*3600)
        return response

    return router
