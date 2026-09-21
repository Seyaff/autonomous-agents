import io
from typing import List
from fastapi import UploadFile, HTTPException, status
from pypdf import PdfReader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


async def process_pdf(file: UploadFile) -> List[Document]:
    """Reads PDF bytes directly from memory and converts pages to LangChain Documents."""
    contents = await file.read()
    
    
    pdf_stream = io.BytesIO(contents)
    reader = PdfReader(pdf_stream)
    
    documents: List[Document] = []
    
    for page_num, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            # Create LangChain Document objects directly
            doc = Document(
                page_content=text,
                metadata={
                    "source": file.filename,
                    "page": page_num
                }
            )
            documents.append(doc)
            
    if not documents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded PDF contains no extractable text."
        )
        
    return documents


async def create_chunks(
    documents: List[Document], 
    chunk_size: int = 1000, 
    chunk_overlap: int = 100
) -> List[Document]:
    """Splits a list of LangChain Documents into smaller overlapping chunks."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""]
    )
    
    chunks = text_splitter.split_documents(documents)
    return chunks