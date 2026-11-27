from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until the token expires


class CurrentUser(BaseModel):
    username: str
    role: str
    authenticated_via: str  # "jwt" or "api_key"
