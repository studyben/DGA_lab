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


def auth_router(service: IdentityService, settings):
    router = APIRouter(prefix='/api/auth')
    origins = set(settings.auth_allowed_origins.split(','))

    def origin(request):
        if request.headers.get('origin') not in origins:
            raise IdentityError('origin_rejected', 403)

    def csrf(request):
        session = service.session(request.cookies.get(COOKIE, ''))
        if not compare_digest(request.headers.get('x-csrf-token', '').encode('utf-8'), session.csrf_token.encode('utf-8')):
            raise IdentityError('csrf_rejected', 403)

    def issue(response, session):
        response.set_cookie(COOKIE, session.token, httponly=True, secure=settings.cookie_secure,
                            samesite='lax', path='/', max_age=settings.session_hours * 3600)
        response.headers['Cache-Control'] = 'no-store'
        return session_body(session)

    @router.post('/login')
    def login(payload: LoginInput, request: Request, response: Response):
        origin(request)
        return issue(response, service.login(payload.username, payload.password))

    @router.get('/session')
    def current(request: Request, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        return session_body(service.session(request.cookies.get(COOKIE, '')))

    @router.post('/password')
    def password(payload: PasswordInput, request: Request, response: Response):
        origin(request)
        csrf(request)
        return issue(response, service.change_password(request.cookies.get(COOKIE, ''), payload.current_password, payload.new_password))

    @router.post('/logout', status_code=204)
    def logout(request: Request):
        origin(request)
        token = request.cookies.get(COOKIE, '')
        try:
            csrf(request)
        except IdentityError as error:
            if error.status != 401:
                raise
        service.logout(token)
        response = Response(status_code=204, headers={'Cache-Control': 'no-store'})
        response.delete_cookie(COOKIE, path='/', secure=settings.cookie_secure, httponly=True, samesite='lax')
        return response

    return router
