from fastapi import APIRouter, HTTPException
from ..models.user import UserCreate, UserResponse

auth_router = APIRouter(tags=['auth'])


@auth_router.post('/register', response_model=UserResponse)
def register(data: UserCreate):
    # TODO: implement registration
    raise HTTPException(status_code=501, detail='Not implemented')


@auth_router.post('/login')
def login():
    # TODO: implement login
    raise HTTPException(status_code=501, detail='Not implemented')
