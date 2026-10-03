import io
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pypdf import PdfReader
from pinecone import Pinecone, ServerlessSpec

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_pinecone import PineconeEmbeddings, PineconeVectorStore
from core.settings import settings
from core.database import get_database
from services.pdf_validator import validate_pdf, PDFValidationError

logger = logging.getLogger(__name__)

INDEX_NAME = "pdf-rag-index"

# Cloud-based embedding model (dimension=1024)
embedding_model = PineconeEmbeddings(
    model="multilingual-e5-large",
    pinecone_api_key=settings.PINECONE_API_KEY,
)

pc = Pinecone(api_key=settings.PINECONE_API_KEY)


def get_pinecone_vectorstore(tenant_id: str) -> PineconeVectorStore:
    """Returns a PineconeVectorStore client pinned strictly to the tenant's isolated namespace."""
    # Ensure the index exists (create it if missing)
    if not pc.has_index(INDEX_NAME):
        pc.create_index(
            name=INDEX_NAME,
            dimension=1024,   # must match your embedding_model output
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1",          # pick the region you use
            ),
        )

    return PineconeVectorStore(
        index_name=INDEX_NAME,
        embedding=embedding_model,
        pinecone_api_key=settings.PINECONE_API_KEY,
        namespace=tenant_id,
    )

def parse_pdf_bytes(file_bytes: bytes, filename: str, tenant_id: str, doc_id: str) -> List[Document]:
    """Extracts text pages from raw PDF bytes and constructs LangChain Documents."""
    pdf_stream = io.BytesIO(file_bytes)
    reader = PdfReader(pdf_stream)

    documents: List[Document] = []
    for page_num, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            doc = Document(
                page_content=text.strip(),
                metadata={
                    "doc_id": doc_id,
                    "tenant_id": tenant_id,
                    "source": filename,
                    "page": page_num + 1,
                    "doc_type": "pdf",
                },
            )
            documents.append(doc)

    return documents


async def ingest_pdf_bytes_for_tenant(
    file_bytes: bytes,
    filename: str,
    tenant_id: str
) -> Dict[str, Any]:
    """
    Parses PDF bytes, splits into overlapping chunks, upserts embeddings
    into Pinecone under the tenant's namespace, and records in MongoDB.
    """
    # Validate PDF first
    is_valid, error_msg = validate_pdf(file_bytes, filename)
    if not is_valid:
        logger.warning(f"PDF validation failed for {filename}: {error_msg}")
        return {"status": "error", "message": error_msg}

    doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    raw_documents = parse_pdf_bytes(file_bytes, filename, tenant_id, doc_id)
    if not raw_documents:
        return {"status": "error", "message": f"Could not extract readable text from '{filename}'."}

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=700,
        chunk_overlap=120,
        separators=["\n\n", "\n", " ", ""],
    )
    chunks = text_splitter.split_documents(raw_documents)

    # Upsert to Pinecone
    vector_store = get_pinecone_vectorstore(tenant_id)
    vector_ids = await vector_store.aadd_documents(chunks)

    # Record in MongoDB tenant_knowledge collection
    try:
        db = get_database()
        knowledge_doc = {
            "doc_id": doc_id,
            "tenant_id": tenant_id,
            "title": filename,
            "doc_type": "pdf",
            "chunks_count": len(chunks),
            "vector_ids": vector_ids,
            "created_at": datetime.now(timezone.utc),
        }
        await db["tenant_knowledge"].insert_one(knowledge_doc)
    except Exception as e:
        logger.warning(f"Could not record knowledge in MongoDB (vectors saved to Pinecone): {e}")

    return {
        "status": "success",
        "doc_id": doc_id,
        "title": filename,
        "full_text": "\n\n".join(d.page_content for d in raw_documents),
        "chunks_indexed": len(chunks),
        "message": f"Successfully indexed '{filename}' ({len(chunks)} chunks) into Pinecone namespace '{tenant_id}'."
    }


async def ingest_text_knowledge_for_tenant(
    title: str,
    content: str,
    tenant_id: str,
    category: str = "faq"
) -> Dict[str, Any]:
    """
    Ingests raw text knowledge (e.g. Store FAQs, special deals, policies, recipes)
    into the tenant's Pinecone namespace.
    """
    if not content.strip():
        return {"status": "error", "message": "Content cannot be empty."}

    doc_id = f"txt_{uuid.uuid4().hex[:8]}"
    doc = Document(
        page_content=content.strip(),
        metadata={
            "doc_id": doc_id,
            "tenant_id": tenant_id,
            "source": title,
            "category": category,
            "doc_type": "text",
        }
    )

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=100,
    )
    chunks = text_splitter.split_documents([doc])

    vector_store = get_pinecone_vectorstore(tenant_id)
    vector_ids = await vector_store.aadd_documents(chunks)

    try:
        db = get_database()
        knowledge_doc = {
            "doc_id": doc_id,
            "tenant_id": tenant_id,
            "title": title,
            "category": category,
            "doc_type": "text",
            "chunks_count": len(chunks),
            "content_snippet": content[:150] + "..." if len(content) > 150 else content,
            "vector_ids": vector_ids,
            "created_at": datetime.now(timezone.utc),
        }
        await db["tenant_knowledge"].insert_one(knowledge_doc)
    except Exception as e:
        logger.warning(f"Could not record knowledge in MongoDB (vectors saved to Pinecone): {e}")

    return {
        "status": "success",
        "doc_id": doc_id,
        "title": title,
        "chunks_indexed": len(chunks),
        "message": f"Successfully indexed '{title}' ({len(chunks)} chunks) into Pinecone."
    }


async def search_tenant_knowledge(query: str, tenant_id: str, top_k: int = 4) -> str:
    """
    Performs similarity search in Pinecone under the tenant's isolated namespace
    and formats verified facts for the AI Agent.
    """
    if not tenant_id:
        return "Notice: No restaurant tenant configured. Knowledge base unavailable."

    try:
        vector_store = get_pinecone_vectorstore(tenant_id)
        results = await vector_store.asimilarity_search_with_score(query=query, k=top_k)

        if not results:
            return "No matching details found in the restaurant's menu, pricing sheets, or store policies."

        formatted_snippets = []
        for doc, score in results:
            source = doc.metadata.get("source", "Knowledge Base")
            page = doc.metadata.get("page")
            header = f"[Source: {source} (Page {page})]" if page else f"[Source: {source}]"
            formatted_snippets.append(f"{header}\n{doc.page_content}")

        return "\n\n---\n\n".join(formatted_snippets)

    except Exception as e:
        logger.error(f"Error querying Pinecone for tenant [{tenant_id}]: {e}")
        return f"Error retrieving knowledge base details: {str(e)}"


async def delete_knowledge_vectors(tenant_id: str, vector_ids: List[str]) -> None:
    """Removes a document's vectors from the tenant's namespace. Raises on failure,
    so the caller keeps the document record and the owner can retry."""
    import asyncio

    if not vector_ids:
        return
    index = pc.Index(INDEX_NAME)
    await asyncio.to_thread(index.delete, ids=vector_ids, namespace=tenant_id)
