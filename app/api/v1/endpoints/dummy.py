from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel
from typing import List
from langchain_groq import ChatGroq
from schemas.dummy import DummyQuery , DummyResponse
from langchain_core.messages import SystemMessage, HumanMessage
from agents.marketing.agent import app
from agents.dummy_agent import (
    process_pdf, 
    create_chunks, 
    store_in_pinecone, 
    search_documents
)

llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0.2)

dummy_router = APIRouter(prefix="/dummy", tags=["Dummy routes"])


class QueryRequest(BaseModel):
    query: str
    top_k: int = 4


@dummy_router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    documents = await process_pdf(file)
    chunks = await create_chunks(documents)
    await store_in_pinecone(chunks)

    return {"message": f"Successfully indexed {len(chunks)} chunks from {file.filename}"}


@dummy_router.post("/search")
async def search_vectorstore(payload: QueryRequest):
    # 1. Retrieve top matching chunks from Pinecone
    docs = await search_documents(query=payload.query, top_k=payload.top_k)
    
    if not docs:
        raise HTTPException(status_code=404, detail="No relevant context found")

  
    context_text = "\n\n---\n\n".join([doc.page_content for doc in docs])

   
    system_prompt = (
        "You are an expert AI assistant. Answer the user's question strictly using "
        "the provided context below. If the answer cannot be found in the context, "
        "state that you do not have enough information.\n\n"
        f"Context:\n{context_text}"
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=payload.query)
    ]

    
    ai_response = await llm.ainvoke(messages)

    
    sources = [
        {
            "content": doc.page_content,
            "metadata": doc.metadata
        }
        for doc in docs
    ]

    return {
        "query": payload.query,
        "answer": ai_response.content,
    }
    
    
    
@dummy_router.post("/agent-query", response_model=DummyResponse)
async def agent_query(query: DummyQuery):
    # Construct input payload
    initial_state = {
        "messages": [HumanMessage(content=query.query)]
    }

    # Execute async pipeline
    final_state = await app.ainvoke(initial_state)

    
    last_message = final_state["messages"][-1]
    response_text = last_message.content if hasattr(last_message, "content") else str(last_message)

    return DummyResponse(response=response_text)