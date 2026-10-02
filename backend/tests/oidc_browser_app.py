"""Isolated browser protocol fixture, NEVER the deployment app entry point.

Uses signed local JWTs through the production validator, not real Okta evidence.
Only the explicitly selected disposable browser database is accepted.
"""
from datetime import datetime, timezone
from urllib.parse import parse_qs

import httpx
from authlib.jose import JsonWebKey, JsonWebToken
from sqlalchemy.engine import make_url
from pydantic import SecretStr

from dga.main import create_app
from dga.shared.config import Settings
from dga.shared.auth.oidc_provider import OktaProvider


def build_app():
    settings = Settings()
    url = make_url(settings.database_url.get_secret_value())
    if (url.host, url.database, url.username) != ('db', 'dga_browser', 'dga_browser'):
        raise RuntimeError('OIDC browser fixture requires disposable browser database')
    # Published fixture key, never a deployment secret. No env flag enables this adapter.
    settings.oidc_encryption_key = SecretStr('LbsTTNRHHGjNpCacJPmxNYIyFVwnX-uviZEgmPMMKaI=')
    settings.oidc_allowed_hosts = 'tenant.example'
    settings.oidc_callback_url = 'http://127.0.0.1:18118/api/auth/oidc/callback'
    private = JsonWebKey.generate_key('RSA', 2048, is_private=True, options={'kid': 'browser-test-key'})
    def transport(request):
        if request.url.path.endswith('openid-configuration'):
            return httpx.Response(200, json={'issuer': 'https://tenant.example',
                'authorization_endpoint': 'https://tenant.example/authorize',
                'token_endpoint': 'https://tenant.example/token', 'jwks_uri': 'https://tenant.example/keys'})
        if request.url.path == '/keys':
            return httpx.Response(200, json={'keys': [private.as_dict(is_private=False)]})
        if request.url.path == '/token':
            code = parse_qs(request.content.decode())['code'][0]
            if code == 'rejected':
                return httpx.Response(400, json={'error': 'invalid_grant'})
            # Browser intercept deliberately sends the flow's nonce as this fixture's code.
            now = int(datetime.now(timezone.utc).timestamp())
            token = JsonWebToken(['RS256']).encode({'alg': 'RS256', 'kid': 'browser-test-key'},
                {'iss': 'https://tenant.example', 'sub': 'browser-employee', 'aud': 'browser-client',
                 'nonce': code, 'iat': now, 'auth_time': now, 'exp': now + 300,
                 'name': 'OIDC browser employee', 'groups': ['system_admin']}, private).decode()
            return httpx.Response(200, json={'id_token': token, 'access_token': 'discard', 'token_type': 'Bearer'})
        raise AssertionError('unexpected fixture request')
    return create_app(settings, oidc_provider=OktaProvider({'tenant.example'}, transport=httpx.MockTransport(transport)))


app = build_app()
