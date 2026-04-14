import datetime
import os
from google.adk.agents.llm_agent import Agent
from google.adk.tools.enterprise_search_tool import EnterpriseWebSearchTool
import vertexai

vertexai.init(
    project=os.environ["GOOGLE_CLOUD_PROJECT"],
    location=os.environ["GOOGLE_CLOUD_LOCATION"]

)



def create_agent() -> Agent:
    return Agent(
        model='gemini-2.5-pro',
        name='q_n_a_agent',
        description="An agent that can help user answer their question base on enterprise search tool",
        instruction=f"""
You are an agent that can help user's question by leverage enterprise search..
""",
        tools=[EnterpriseWebSearchTool()],
    )

