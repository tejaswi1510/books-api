"""Login endpoint: username + password in, JWT out."""
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import get_auth_service
from app.core.security import Principal, get_current_principal
from app.schemas.auth import CurrentUser, Token
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=Token, summary="Log in and get an access token")
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> Token:
    # OAuth2PasswordRequestForm reads form fields (not JSON): username and password.
    return service.login(form.username, form.password)


@router.get("/me", response_model=CurrentUser, summary="Who am I? (needs a token)")
def me(principal: Annotated[Principal, Depends(get_current_principal)]) -> CurrentUser:
    return CurrentUser(
        username=principal.username, role=principal.role, authenticated_via=principal.via
    )
