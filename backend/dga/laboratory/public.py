"""Public application entry; business capabilities arrive in owning tickets."""
from dga.shared.contracts import ModuleDescriptor
from dga.shared.auth.public import ActorContext, require_permission

MODULE = ModuleDescriptor(code='laboratory', label='DGA 实验室')


def access_context(actor: ActorContext) -> dict:
    require_permission(actor, 'laboratory.read')
    return {'module': MODULE.code, 'actor_id': str(actor.user_id)}
