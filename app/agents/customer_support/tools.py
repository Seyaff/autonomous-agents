import uuid
from datetime import datetime, timezone
from typing import Optional, List
from langchain_core.tools import tool
from pymongo.errors import PyMongoError
from core.database import get_database
from langchain_pinecone import PineconeVectorStore

@tool
async def create_order_tool(
    tenant_id: str,
    customer_phone: str,
    delivery_address: str,
    items: List[dict],
    total_amount: float,
    payment_method: str = "cod",
    customer_notes: Optional[str] = None
) -> str:
    """Creates and saves a new customer order to the database.

    Args:
        tenant_id: The unique identifier for the tenant.
        customer_phone: Customer's contact phone number.
        delivery_address: Destination address for delivery.
        items: List of ordered items. Each dict MUST contain 'name', 'quantity', and 'price' keys.
               Example: [{"name": "Pepperoni Pizza", "quantity": 1, "price": 12.50}]
        total_amount: Calculated total cost of the order.
        payment_method: Chosen payment method (e.g. "cod", "card"). Default is "cod".
        customer_notes: Optional delivery instructions or notes.
    """
    try:
        db = get_database()
        
        # Format and validate items list
        formatted_items = []
        for item in items:
            formatted_items.append({
                "name": str(item.get("name", "Unknown Item")),
                "quantity": int(item.get("quantity", 1)),
                "price": float(item.get("price", 0.0)),
                "notes": item.get("notes")
            })

        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"

        order_document = {
            "order_id": order_id,
            "tenant_id": tenant_id,
            "customer_phone": customer_phone,
            "delivery_address": delivery_address,
            "items": formatted_items,
            "total_amount": float(total_amount),
            "payment_method": payment_method,
            "customer_notes": customer_notes,
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        result = await db["orders"].insert_one(order_document)

        if result.inserted_id:
            return f"Order placed successfully! Reference ID: {order_id}. Total: ${total_amount:.2f}."
        
        return "Could not record order in database."

    except PyMongoError as e:
        return f"Database error: {str(e)}"
    except Exception as e:
        return f"Failed to create order: {str(e)}"
    
    
@tool
async def search_uploaded_documents(query: str, config: dict) -> str:
    """Searches uploaded PDFs, live menus, pricing sheets, and policies for contextual answers."""
    # Retrieve tenant_id dynamically from agent execution config
    tenant_id = config.get("configurable", {}).get("thread_id")
    if not tenant_id:
        return "Tenant session missing. Cannot query knowledge base."

    try:
        # Target Pinecone vector store using caller's namespace
        vector_store = PineconeVectorStore(
            index_name="pdf-rag-index",
            embedding=embedding_model,
            pinecone_api_key=settings.PINECONE_API_KEY,
            namespace=tenant_id,
        )

        results = await vector_store.asimilarity_search(query=query, k=4)
        if not results:
            return "No matching details found in uploaded documents or live menus."

        formatted_chunks = []
        for doc in results:
            source = doc.metadata.get("source", "PDF Document")
            page = doc.metadata.get("page", 1)
            formatted_chunks.append(f"[Source: {source} (Page {page})]\n{doc.page_content}")

        return "\n\n---\n\n".join(formatted_chunks)

    except Exception as e:
        return f"Error retrieving knowledge base details: {str(e)}"