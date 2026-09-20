import os
import operator
from typing import Annotated
from typing_extensions import TypedDict

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import AnyMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver


from deepagents import create_deep_agent
from agents.customer_support.prompt import CUSTOMER_SUPPORT_SYSTEM_PROMPT
from agents.customer_support.tools import create_order_tool

load_dotenv()

# Initialize LLM
model = ChatGroq(model="openai/gpt-oss-120b")

# Define Graph State
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]

# Node function that delegates execution to deepagent
async def agent_node(state: AgentState):
    agent = create_deep_agent(
        model=model,
        system_prompt=CUSTOMER_SUPPORT_SYSTEM_PROMPT,
        tools=[create_order_tool]
    )
    # Invoke deepagent with current message state
    result = await agent.ainvoke({"messages": state["messages"]})
    
    # Extract response messages from deepagent output
    new_messages = result.get("messages", [])
    return {"messages": new_messages}

# Build LangGraph workflow
customer_graph = StateGraph(AgentState)

customer_graph.add_node("chat_agent", agent_node)
customer_graph.add_edge(START, "chat_agent")
customer_graph.add_edge("chat_agent", END)

checkpointer = MemorySaver()

# Export compiled graph as master_agent
master_agent = customer_graph.compile(checkpointer=checkpointer)