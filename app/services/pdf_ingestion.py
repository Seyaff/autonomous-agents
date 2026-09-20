import io
from typing import List
from pypdf import PdfReader
from pinecone import Pinecone

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from core.settings import settings

# Global embedding model (384 dimensions)
embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

pc = Pinecone(api_key=settings.PINECONE_API_KEY)


def verify_and_get_index(index_name: str = "pdf-rag-index"):
    """Ensures Pinecone index exists before executing vector operations."""
    existing_indexes = [index.name for index in pc.list_indexes()]
    if index_name not in existing_indexes:
        raise ValueError(f"Index '{index_name}' does not exist in Pinecone!")
    return pc.Index(index_name)


def parse_pdf_bytes(file_bytes: bytes, filename: str, tenant_id: str) -> List[Document]:
    """Reads PDF bytes from memory and creates LangChain Document objects tagged with tenant_id."""
    pdf_stream = io.BytesIO(file_bytes)
    reader = PdfReader(pdf_stream)

    documents: List[Document] = []
    for page_num, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            doc = Document(
                page_content=text,
                metadata={
                    "tenant_id": tenant_id,
                    "source": filename,
                    "page": page_num + 1,
                },
            )
            documents.append(doc)

    return documents


async def process_and_store_pdf_bytes(
    file_bytes: bytes,
    filename: str,
    tenant_id: str,
    index_name: str = "pdf-rag-index",
) -> int:
    """Parses PDF bytes, creates chunks, and upserts embeddings into Pinecone namespace."""
    verify_and_get_index(index_name)

    documents = parse_pdf_bytes(file_bytes, filename, tenant_id)
    if not documents:
        return 0

    # Split document into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
        separators=["\n\n", "\n", " ", ""],
    )
    chunks = text_splitter.split_documents(documents)

    # Initialize vector store tied specifically to tenant's isolated namespace
    vector_store = PineconeVectorStore(
        index_name=index_name,
        embedding=embedding_model,
        pinecone_api_key=settings.PINECONE_API_KEY,
        namespace=tenant_id,
    )

    ids = await vector_store.aadd_documents(chunks)
    return len(ids)