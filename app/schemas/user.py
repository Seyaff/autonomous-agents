from pydantic import BaseModel, Field, EmailStr
from enum import Enum
from typing import Optional

class CreateUser(BaseModel):
    name: str = Field(
        ..., 
        min_length=2, 
        max_length=50, 
        description="The full name of the user to create"
    )
    email: EmailStr = Field(
        ..., 
        description="The unique email address of the user"
    )
    password: str = Field(
        ..., 
        min_length=8, 
        max_length=128, 
        description="User account password (min 8 characters)"
    )
    

class UserResponse(BaseModel):
    id: str = Field(..., description="The MongoDB string ID of the created user")
    name: str
    email: EmailStr
    
    class Config:
        from_attributes = True  # Allows ORM/MongoDB document mapping