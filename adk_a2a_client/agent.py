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

from google.adk.agents.llm_agent import Agent
from google.genai import types
from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.apps.app import App
import httpx
import os
import vertexai

vertexai.init(
    project=os.environ["GOOGLE_CLOUD_PROJECT"],
    location=os.environ["GOOGLE_CLOUD_LOCATION"]

)


class TokenRefreshAuth(httpx.Auth):
    """httpx.Auth implementation that supports Azure AD OAuth2 token refresh.

    On a 401 response the auth handler will POST to the Azure token endpoint
    using the standard OAuth2 refresh-token grant
    (https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow#refresh-the-access-token)
    and retry the original request with the new access token.

    Required Azure token-endpoint parameters
    -----------------------------------------
    client_id     : Application (client) ID registered in Azure AD.
    client_secret : Client secret for the registered application.
    scope         : Space-separated list of scopes (e.g. ``"api://<app-id>/.default"``).
    """

    requires_response_body = True

    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: str,
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope

    async def _async_refresh_token(self) -> None:
        """Exchange the current refresh token for a new access (and refresh) token.

        Follows the Azure AD OAuth2 refresh-token grant:
        https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow#refresh-the-access-token
        """
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.token_url,
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": self.scope,
                    "refresh_token": self.refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data["access_token"]
        # Azure may rotate the refresh token; persist the latest one when present.
        if "refresh_token" in data:
            self.refresh_token = data["refresh_token"]

    async def async_auth_flow(self, request):
        request.headers["Authorization"] = f"Bearer {self.access_token}"
        response = yield request

        if response.status_code == 401:
            try:
                await self._async_refresh_token()
            except httpx.HTTPStatusError:
                # refresh itself failed (e.g. refresh token expired)
                # return the original 401 response without retrying
                return

            request.headers["Authorization"] = f"Bearer {self.access_token}"

            try:
                # second yield; catch network errors
                response = yield request
            except httpx.RequestError:
                raise  # or do fallback handling

            # still failing on second attempt? let the caller handle it
            if response.status_code != 200:
                response.raise_for_status()

_auth = TokenRefreshAuth(
    access_token=os.environ["OAUTH_ACCESS_TOKEN"],
    refresh_token=os.environ["OAUTH_REFRESH_TOKEN"],
    token_url=os.environ["OAUTH_TOKEN_URL"],
    client_id=os.environ["OAUTH_CLIENT_ID"],
    client_secret=os.environ["OAUTH_CLIENT_SECRET"],
    scope=os.environ["OAUTH_SCOPE"],
)

_httpx_client = httpx.AsyncClient(
    auth=_auth,
    timeout=httpx.Timeout(timeout=600.0),
)

a2a_qna_agent = RemoteA2aAgent(
    name="qna_agent",
    description="An agent that can help user answer their question base on enterprise search tool.",
    agent_card=(
        f"http://localhost:10007{AGENT_CARD_WELL_KNOWN_PATH}"
    ),
    httpx_client=_httpx_client,
    timeout=600.0,
    use_legacy=False,
)

root_agent = Agent(
    model="gemini-2.5-pro",
    name="root_agent",
    instruction="""
      You are a helpful assistant that canhelp user answer their questions
      1. If the user asks the knowledge out side your knowledge, delegate to the a2a_qna_agent.
    """,
    sub_agents=[a2a_qna_agent],
)

app = App(name="adk_a2a_client", root_agent=root_agent)