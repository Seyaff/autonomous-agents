from fastapi import APIRouter, File ,UploadFile, HTTPException, status
from rag.pdf_processor import process_pdf, create_chunks
from rag.embeddings import embed_and_store_chunks


tenant_routes = APIRouter(prefix="/tenant" , tags=["tenant"])


@tenant_routes.post("/inject-data")
async def inject_data(file : UploadFile = File(...)):
    
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only PDF files are allowed."
        )
        
        
    raw_docs = await process_pdf(file)
    
    # 2. Chunk documents for vector storage
    chunks = await create_chunks(raw_docs, chunk_size=800, chunk_overlap=150)
    
    for chunk in chunks:
        print(chunk)
        break
    
     
    
    bro = await embed_and_store_chunks(chunks)
    print(bro)
    
    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "message": "PDF uploaded successfully"
    }