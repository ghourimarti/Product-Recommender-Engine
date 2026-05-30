from pydantic import BaseModel, Field


class AuthRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)


class RecommendRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Natural language description of anime preferences",
        examples=["dark psychological thriller with morally complex characters"],
    )
