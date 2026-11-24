"""Login endpoint: username + password in, JWT out."""
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import get_auth_service
from app.schemas.auth import Token
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=Token, summary="Log in and get an access token")
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> Token:
    # OAuth2PasswordRequestForm reads form fields (not JSON): username and password.
    return service.login(form.username, form.password)
