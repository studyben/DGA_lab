"""External protocol adapter: allowlisted HTTPS, Authorization Code/PKCE, signed OIDC claims."""
from dataclasses import dataclass
from math import isfinite
from typing import Protocol

import httpx
from authlib.integrations.httpx_client import OAuth2Client
from authlib.jose import JsonWebToken
from authlib.oidc.core import CodeIDToken

from .public import IdentityError


@dataclass(frozen=True)
class VerifiedIdentity:
    issuer: str
    subject: str
    display_name: str
    login_hints: tuple[str, ...]


class OidcProvider(Protocol):
    def authorization_url(self, config, *, callback, state, nonce, verifier) -> str: ...
    def redeem(self, config, *, callback, code, nonce, verifier, issued_at, clock) -> VerifiedIdentity: ...


class OktaProvider:
    def __init__(self, allowed_hosts, *, transport=None):
        self._hosts = frozenset(allowed_hosts)
        # Injection only for in-process tests; never a runtime flag or HTTP option.
        self._transport = transport

    def _url(self, value):
        from .oidc import checked_url
        return checked_url(value, self._hosts)

    def _client(self, config, callback):
        return OAuth2Client(config['client_id'], config.get('client_secret'),
            redirect_uri=callback, scope='openid profile email', code_challenge_method='S256',
            token_endpoint_auth_method='client_secret_basic', timeout=10, follow_redirects=False,
            trust_env=False, transport=self._transport)

    def _json(self, client, url):
        response = client.request('GET', self._url(url), withhold_token=True)
        response.raise_for_status()
        if len(response.content) > 1024 * 1024:
            raise ValueError('oversize provider response')
        value = response.json()
        if not isinstance(value, dict):
            raise ValueError('invalid provider response')
        return value

    def _metadata(self, client, issuer):
        metadata = self._json(client, self._url(issuer) + '/.well-known/openid-configuration')
        if metadata.get('issuer') != issuer:
            raise ValueError('issuer mismatch')
        for key in ('authorization_endpoint', 'token_endpoint', 'jwks_uri'):
            self._url(metadata[key])
        return metadata

    def authorization_url(self, config, *, callback, state, nonce, verifier):
        try:
            with self._client(config, callback) as client:
                metadata = self._metadata(client, config['issuer'])
                url, _ = client.create_authorization_url(metadata['authorization_endpoint'], state=state,
                    nonce=nonce, code_verifier=verifier, prompt='login', max_age=0)
                return url
        except Exception:
            # Provider exceptions may include tokens, URLs or secrets. Do not expose or log them.
            raise IdentityError('oidc_provider_rejected', 502) from None

    def redeem(self, config, *, callback, code, nonce, verifier, issued_at, clock):
        try:
            with self._client(config, callback) as client:
                metadata = self._metadata(client, config['issuer'])
                # Obtain trusted public keys before fetch_token installs an access token in this client.
                keys = self._json(client, metadata['jwks_uri'])['keys']
                if not isinstance(keys, list) or not 1 <= len(keys) <= 100:
                    raise ValueError('invalid keyset')
                token = client.fetch_token(metadata['token_endpoint'], grant_type='authorization_code',
                    code=code, code_verifier=verifier)
                raw = token.get('id_token')
                if not isinstance(raw, str) or len(raw) > 32768:
                    raise ValueError('missing token')
                def signing_key(header, payload):
                    kid = header.get('kid')
                    matching = [key for key in keys if isinstance(key, dict) and key.get('kid') == kid
                        and key.get('kty') == 'RSA' and key.get('use', 'sig') == 'sig'
                        and key.get('alg', 'RS256') == 'RS256']
                    if not isinstance(kid, str) or not kid or len(matching) != 1:
                        raise ValueError('invalid signing key')
                    return matching[0]
                claims = JsonWebToken(['RS256']).decode(raw, signing_key, claims_cls=CodeIDToken,
                    claims_options={'iss': {'essential': True, 'value': config['issuer']},
                        'sub': {'essential': True}, 'exp': {'essential': True}, 'iat': {'essential': True},
                        'aud': {'essential': True}, 'auth_time': {'essential': True}, 'nonce': {'essential': True}},
                    claims_params={'client_id': config['client_id'], 'nonce': nonce, 'access_token': token.get('access_token')})
                now = clock()
                claims.validate(now=now.timestamp(), leeway=0)
                audiences = claims['aud'] if isinstance(claims['aud'], list) else [claims['aud']]
                if config['client_id'] not in audiences or not all(isinstance(a, str) for a in audiences):
                    raise ValueError('audience mismatch')
                if (len(audiences) > 1 or 'azp' in claims) and claims.get('azp') != config['client_id']:
                    raise ValueError('party mismatch')
                for key in ('iat', 'auth_time', 'exp'):
                    if type(claims[key]) not in (int, float) or not isfinite(claims[key]):
                        raise ValueError('invalid timestamp')
                if not (issued_at.timestamp() - 60 <= claims['auth_time'] <= now.timestamp() + 60
                    and issued_at.timestamp() - 60 <= claims['iat'] <= now.timestamp() + 60
                    and claims['exp'] > now.timestamp() and claims['exp'] > claims['iat']):
                    raise ValueError('stale login')
                subject = claims['sub']
                if not isinstance(subject, str) or not 1 <= len(subject) <= 255:
                    raise ValueError('invalid subject')
                name = claims.get('name')
                hints = tuple({value.strip().lower() for value in (claims.get('preferred_username'), claims.get('email'))
                    if isinstance(value, str) and 1 <= len(value.strip()) <= 320})
                return VerifiedIdentity(config['issuer'], subject,
                    name[:150] if isinstance(name, str) and name.strip() else 'Okta employee',
                    hints)
        except Exception:
            raise IdentityError('oidc_provider_rejected', 502) from None
