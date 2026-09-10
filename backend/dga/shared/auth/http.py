"""HTTP transport for the shared identity application interface."""
from secrets import compare_digest

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from .public import IdentityError, IdentityService, Session

COOKIE = 'dga_session'


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)


class PasswordInput(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=15, max_length=128)


def session_body(session: Session):
    actor = session.actor
    return dict(actor=dict(id=str(actor.user_id), username=actor.username, display_name=actor.display_name),
                roles=sorted(actor.roles), permissions=sorted(actor.permissions),
                must_change_password=actor.must_change_password, csrf_token=session.csrf_token,
                expires_at=session.expires_at.isoformat())


class AuthenticatedRequests:
    """One HTTP security policy for session reads and same-origin mutations."""

    def __init__(self, service: IdentityService, settings):
        self._service = service
        self._origins = set(settings.auth_allowed_origins.split(','))

    def require_origin(self, request: Request) -> None:
        if request.headers.get('origin') not in self._origins:
            raise IdentityError('origin_rejected', 403)

    def session(self, request: Request) -> Session:
        return self._service.session(request.cookies.get(COOKIE, ''))

    def csrf_session(self, request: Request) -> Session:
        self.require_origin(request)
        session = self.session(request)
        supplied = request.headers.get('x-csrf-token', '').encode('utf-8')
        if not compare_digest(supplied, session.csrf_token.encode('utf-8')):
            raise IdentityError('csrf_rejected', 403)
        return session

    def actor(self, request: Request):
        actor = self.session(request).actor
        if actor.must_change_password:
            raise IdentityError('password_change_required', 403)
        return actor

    def mutation_actor(self, request: Request):
        actor = self.csrf_session(request).actor
        if actor.must_change_password:
            raise IdentityError('password_change_required', 403)
        return actor


def auth_router(
    service: IdentityService,
    settings,
    requests: AuthenticatedRequests | None = None,
):
    router = APIRouter(prefix='/api/auth')
    requests = requests or AuthenticatedRequests(service, settings)

    def issue(response, session):
        response.set_cookie(COOKIE, session.token, httponly=True, secure=settings.cookie_secure,
                            samesite='lax', path='/', max_age=settings.session_hours * 3600)
        response.headers['Cache-Control'] = 'no-store'
        return session_body(session)

    @router.post('/login')
    def login(payload: LoginInput, request: Request, response: Response):
        requests.require_origin(request)
        return issue(response, service.login(payload.username, payload.password))

    @router.get('/session')
    def current(request: Request, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        return session_body(requests.session(request))

    @router.post('/password')
    def password(payload: PasswordInput, request: Request, response: Response):
        requests.csrf_session(request)
        return issue(response, service.change_password(request.cookies.get(COOKIE, ''), payload.current_password, payload.new_password))

    @router.post('/logout', status_code=204)
    def logout(request: Request):
        token = request.cookies.get(COOKIE, '')
        try:
            requests.csrf_session(request)
        except IdentityError as error:
            if error.status != 401:
                raise
        service.logout(token)
        response = Response(status_code=204, headers={'Cache-Control': 'no-store'})
        response.delete_cookie(COOKIE, path='/', secure=settings.cookie_secure, httponly=True, samesite='lax')
        return response

    return router
