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
    requires_response_body = True

    def __init__(self, access_token, refresh_token, token_url):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_url = token_url

    async def _async_refresh_token(self):
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.token_url, data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            })
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data["access_token"]

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
    refresh_token=os.environ["OAUTH_FERESH_TOKEN"],
    token_url=os.environ["OAUTH_TOKEN_URL"],
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