"""Base models."""
from pydantic import BaseModel, ConfigDict

class CoreModel(BaseModel):
    """Base model for all domain models."""
    model_config = ConfigDict(
        validate_assignment=True,
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )
