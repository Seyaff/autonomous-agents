from langchain_groq import ChatGroq
from langchain.agents import create_agent
from agents.leads.tools import scrape_leads
from langgraph.graph import StateGraph , START , END











llm = ChatGroq(model="openai/gpt-oss-120b")



agent = create_agent(
    model=llm,
    system_prompt="You are a lead gen agent",
    tools=[scrape_leads]
)






