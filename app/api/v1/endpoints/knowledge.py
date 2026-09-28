import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel, Field

from core.database import get_database
from middlewares.auth_middleware import get_current_user
from services.knowledge_ingestion import (
    ingest_pdf_bytes_for_tenant,
    ingest_text_knowledge_for_tenant,
    search_tenant_knowledge
)

logger = logging.getLogger(__name__)

knowledge_router = APIRouter(prefix="/tenant/knowledge", tags=["Tenant Knowledge & RAG"])


class TextKnowledgePayload(BaseModel):
    title: str = Field(..., min_length=2, example="Weekend BBQ Specials")
    content: str = Field(..., min_length=5, example="On Saturdays and Sundays, all BBQ platters come with complimentary mint margarita.")
    category: str = Field("deal", example="deal")  # deal, policy, recipe, faq


class SearchTestPayload(BaseModel):
    query: str = Field(..., example="Do you have any gluten free pasta or pizza?")


@knowledge_router.post("/upload-pdf")
async def upload_pdf_knowledge(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Uploads a menu PDF, policy document, or pricing sheet,
    chunks it, and indexes into the tenant's Pinecone namespace.
    """
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active restaurant profile linked to your account."
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a PDF document."
        )

    try:
        file_bytes = await file.read()
        result = await ingest_pdf_bytes_for_tenant(
            file_bytes=file_bytes,
            filename=file.filename,
            tenant_id=tenant_id
        )

        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))

        return result

    except Exception as e:
        logger.error(f"Error ingesting PDF for tenant [{tenant_id}]: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process and index PDF: {str(e)}")


@knowledge_router.post("/add-text")
async def add_text_knowledge(
    payload: TextKnowledgePayload,
    current_user: dict = Depends(get_current_user)
):
    """
    Directly adds structured text knowledge (e.g. deals, allergen alerts, FAQs)
    to the restaurant's Pinecone knowledge base.
    """
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active restaurant profile linked to your account."
        )

    result = await ingest_text_knowledge_for_tenant(
        title=payload.title,
        content=payload.content,
        tenant_id=tenant_id,
        category=payload.category
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))

    return result


@knowledge_router.get("")
async def list_tenant_knowledge(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Lists all active knowledge documents, menus, and text snippets for the restaurant."""
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant linked to user.")

    cursor = db["tenant_knowledge"].find({"tenant_id": tenant_id}).sort("created_at", -1)
    documents = await cursor.to_list(length=100)

    for doc in documents:
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])

    return {
        "status": "success",
        "tenant_id": tenant_id,
        "total": len(documents),
        "documents": documents
    }


@knowledge_router.delete("/{doc_id}")
async def delete_tenant_knowledge(
    doc_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_database)
):
    """Deletes a knowledge document reference from MongoDB."""
    tenant_id = current_user.get("active_tenant_id")
    res = await db["tenant_knowledge"].delete_one({"doc_id": doc_id, "tenant_id": tenant_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Document not found.")

    return {"status": "success", "message": f"Document '{doc_id}' deleted."}


@knowledge_router.post("/test-search")
async def test_search_knowledge(
    payload: SearchTestPayload,
    current_user: dict = Depends(get_current_user)
):
    """
    Enables restaurant owners to test-query their Pinecone knowledge base directly
    to verify what snippets the AI customer support agent will retrieve.
    """
    tenant_id = current_user.get("active_tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="No active tenant linked to user.")

    context = await search_tenant_knowledge(query=payload.query, tenant_id=tenant_id, top_k=4)
    return {
        "status": "success",
        "query": payload.query,
        "retrieved_context": context
    }
