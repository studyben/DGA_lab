"""User-management transport; authorization belongs to IdentityService."""
from uuid import UUID
from typing import Literal

from fastapi import APIRouter, Request, Response, Depends
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from .http import AuthenticatedRequests
from .public import IdentityService


class StrictInput(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ProfileInput(StrictInput):
    display_name: str = Field(min_length=1, max_length=150)
    expected_revision: StrictInt = Field(ge=0)


class RolesInput(StrictInput):
    add: list[str] = Field(max_length=10)
    remove: list[str] = Field(max_length=10)
    expected_revision: StrictInt = Field(ge=0)


class StatusInput(StrictInput):
    status: Literal['ACTIVE', 'LOCKED', 'DISABLED']
    expected_revision: StrictInt = Field(ge=0)


class RecoveryInput(StrictInput):
    username: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=15, max_length=128, repr=False)


def management_router(service: IdentityService, requests: AuthenticatedRequests):
    def no_cache(response: Response):
        response.headers['Cache-Control'] = 'no-store'

    router = APIRouter(prefix='/api/auth', dependencies=[Depends(no_cache)])

    @router.get('/users')
    def users(request: Request, query: str = '', status: str | None = None,
              role: str | None = None, page: int = 1):
        return service.list_users(requests.actor(request), query=query, status=status, role=role, page=page)

    @router.put('/users/{user_id}/profile')
    def profile(user_id: UUID, payload: ProfileInput, request: Request):
        actor = requests.mutation_actor(request)
        service.update_profile(actor, user_id, payload.display_name, expected_revision=payload.expected_revision)
        return {'updated': True}

    @router.get('/roles')
    def roles(request: Request):
        return service.role_catalog(requests.actor(request))

    @router.get('/users/{user_id}')
    def detail(user_id: UUID, request: Request):
        return service.user_detail(requests.actor(request), user_id)

    @router.post('/users/recovery', status_code=201)
    def recovery(payload: RecoveryInput, request: Request):
        user_id = service.provision_user(requests.mutation_actor(request), payload.username,
            payload.display_name, payload.password, ['system_admin'])
        return {'id': str(user_id)}

    @router.put('/users/{user_id}/roles')
    def change_roles(user_id: UUID, payload: RolesInput, request: Request):
        service.change_roles(requests.mutation_actor(request), user_id, add=payload.add,
                             remove=payload.remove, expected_revision=payload.expected_revision)
        return {'updated': True}

    @router.put('/users/{user_id}/status')
    def status(user_id: UUID, payload: StatusInput, request: Request):
        service.set_status(requests.mutation_actor(request), user_id, payload.status,
                           expected_revision=payload.expected_revision)
        return {'updated': True}

    return router
