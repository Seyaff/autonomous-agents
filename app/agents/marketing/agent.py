from typing import Annotated, Sequence, TypedDict, Union
from langchain_core.messages import BaseMessage
from langchain_groq import ChatGroq
from langchain.tools import tool
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages
from langchain.agents import create_agent

from core.database import get_database
from schemas.user import CreateUser

model = ChatGroq(model="openai/gpt-oss-120b", temperature=0)


class MasterState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    name: str


@tool
async def create_user(user_data: Union[CreateUser, dict]) -> str:
    """Creates a user in the database and returns a summary of the created user profile."""

    db = get_database()
    users = db["users"]
    user_dict = user_data.model_dump()
    email = user_dict.get("email", "").strip().lower()
    name = user_dict.get("name", "").strip()

    existing_user = await users.find_one({"email": email})
    if existing_user:
        return f"User creation failed: An account with email '{email}' already exists."

    result = await users.insert_one(user_dict)

    user_name = getattr(user_data, "name", "New User")
    return f"Successfully created user with ID: {result.inserted_id} for user '{user_name}'"


@tool
async def update_user(user_data: Union[CreateUser, dict]) -> str:
    """Updates an existing user's details in the database by email."""
    
    # 1. Convert to Pydantic model if passed as raw dict from agent
    if isinstance(user_data, dict):
        user_data = CreateUser.model_validate(user_data)

    # 2. Extract and normalize fields
    email = user_data.email.strip().lower()
    name = user_data.name.strip()
    raw_password = user_data.password.strip()

    db = get_database()
    users = db["users"]

   
    existing_user = await users.find_one({"email": email})
    if not existing_user:
        return f"User update failed: No account found with email '{email}'."

    update_data = {
        "name": name,
        "email": email,
        "password": raw_password
    }

    result = await users.update_one(
        {"email": email},          # Filter: locate target document
        {"$set": update_data}       # Update operator
    )

    if result.modified_count > 0:
        return f"Successfully updated user profile for '{email}'."
    
    return f"No changes were made to user '{email}'."

agent = create_agent(
    model=model,
    tools=[create_user],
    system_prompt="You are a helpful customer support assistant. Your job is to help with any queries users give you. If you cannot do something the user asks for, simply respond and say you will escalate their query to a human.",
)


async def customer_support_node(state: MasterState):
    messages = state["messages"]

    response = await agent.ainvoke({"messages": messages})

    return response


agent_graph = StateGraph(MasterState)
agent_graph.add_node("customer_support", customer_support_node)

agent_graph.add_edge(START, "customer_support")
agent_graph.add_edge("customer_support", END)

app = agent_graph.compile()
