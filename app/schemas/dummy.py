from pydantic import BaseModel

class DummyResponse(BaseModel):
    response:str
    
    
class DummyQuery(BaseModel):
    query:str
    
    
    