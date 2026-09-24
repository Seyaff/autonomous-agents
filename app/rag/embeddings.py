import io
from typing import List
from fastapi import UploadFile, HTTPException, status
from pypdf import PdfReader
from pinecone import Pinecone

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_pinecone import PineconeVectorStore, PineconeEmbeddings

from core.settings import settings

# 1. Cloud-hosted Inference (Zero local RAM overhead, eliminates PyTorch OOM)
# Uses Pinecone's standard 1024/384-dim cloud embedding endpoints
embedding_model = PineconeEmbeddings(
    model="llama-text-embed-v2",
    pinecone_api_key=settings.PINECONE_API_KEY,
)

pc = Pinecone(api_key=settings.PINECONE_API_KEY)


def verify_and_get_index_info(index_name: str = "pdf-rag-index"):
    """Inspects the Pinecone index using the SDK."""
    existing_indexes = [index.name for index in pc.list_indexes()]

    if index_name not in existing_indexes:
        raise ValueError(
            f"Index '{index_name}' does not exist in Pinecone! Available: {existing_indexes}"
        )

    index = pc.Index(index_name)
    stats = index.describe_index_stats()

    print(f"Connected to Pinecone Index: {index_name}")
    print(f"Total Vector Count: {stats.total_vector_count}")
    print(f"Dimension: {stats.dimension}")

    return index


async def process_pdf(file: UploadFile, tenant_id: str) -> List[Document]:
    """Reads PDF bytes from memory and creates Documents tagged with tenant_id."""
    contents = await file.read()
    pdf_stream = io.BytesIO(contents)
    reader = PdfReader(pdf_stream)

    documents: List[Document] = []

    for page_num, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            doc = Document(
                page_content=text,
                metadata={
                    "tenant_id": tenant_id,  # CRITICAL for multi-tenant isolation
                    "source": file.filename,
                    "page": page_num + 1,
                },
            )
            documents.append(doc)

    if not documents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded PDF contains no extractable text.",
        )

    return documents


async def create_chunks(
    documents: List[Document],
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> List[Document]:
    """Splits Documents into overlapping chunks while preserving tenant metadata."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )

    return text_splitter.split_documents(documents)


async def embed_and_store_chunks(
    chunks: List[Document],
    tenant_id: str = "bro-tenanth+",
    index_name: str = "pdf-rag-index",
) -> int:
    """Generates cloud embeddings and upserts chunks into Pinecone under the tenant's namespace."""
    if not chunks:
        return 0

    verify_and_get_index_info(index_name)

    # Ensure every chunk explicitly carries tenant metadata
    for chunk in chunks:
        chunk.metadata["tenant_id"] = tenant_id

    # Store vectors inside a tenant-specific namespace
    vector_store = PineconeVectorStore(
        index_name=index_name,
        embedding=embedding_model,
        pinecone_api_key=settings.PINECONE_API_KEY,
        namespace=tenant_id,
    )

    ids = await vector_store.aadd_documents(chunks)
    return len(ids)