# Copyright 2026 Micron Technology, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from adk_agent import create_agent  # type: ignore[import-not-found]
import click
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    BaseUser,
    SimpleUser,
)
from starlette.requests import HTTPConnection, Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.middleware.authentication import AuthenticationMiddleware
import base64
import json
import time
import uvicorn

_PUBLIC_PATHS = {
    '/.well-known/agent-card.json',
    '/.well-known/agent.json',  # deprecated alias
}

def _on_auth_error(request: Request, exc: AuthenticationError) -> Response:
    """Return HTTP 401 Unauthorized when authentication fails."""
    return JSONResponse(
        {'error': 'Unauthorized', 'detail': str(exc)},
        status_code=401,
        headers={'WWW-Authenticate': 'Bearer'},
    )

class SelectiveAuthMiddleware:
    """Wraps AuthenticationMiddleware so that public paths bypass authentication
    entirely, while all other paths are handled by the inner middleware."""

    def __init__(self, app: ASGIApp, backend: AuthenticationBackend) -> None:
        self._public_app = app
        self._auth_app = AuthenticationMiddleware(
            app, backend=backend, on_error=_on_auth_error
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] == 'http' and scope.get('path') in _PUBLIC_PATHS:
            await self._public_app(scope, receive, send)
        else:
            await self._auth_app(scope, receive, send)

class InsecureJWTAuthBackend(AuthenticationBackend):
    """An example implementation of a JWT-based authentication backend."""

    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, BaseUser] | None:
        # For illustrative purposes only: please validate your JWTs!
        auth_header = conn.headers.get('Authorization')
        if not auth_header:
            raise AuthenticationError('Missing Authorization header.')
        try:
            jwt = auth_header.split('Bearer ')[1]
            jwt_claims = jwt.split('.')[1]
            missing_padding = len(jwt_claims) % 4
            if missing_padding:
                jwt_claims += '=' * (4 - missing_padding)
            payload = base64.urlsafe_b64decode(jwt_claims).decode('utf-8')
            parsed_payload = json.loads(payload)
            exp = parsed_payload.get('exp')
            if exp is not None and time.time() > exp:
                raise AuthenticationError('Token has expired.')
            return AuthCredentials([]), SimpleUser(parsed_payload['upn'])
        except AuthenticationError:
            raise
        except Exception as exc:
            raise AuthenticationError('Invalid or malformed token.') from exc



@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=10007)
def main(host: str, port: int):
    root_agent = create_agent()
    # Make your agent A2A-compatible
    a2a_app = to_a2a(root_agent, port=port)
    app = SelectiveAuthMiddleware(a2a_app, backend=InsecureJWTAuthBackend())
    uvicorn.run(app, host=host, port=port)

if __name__ == '__main__':
    main()