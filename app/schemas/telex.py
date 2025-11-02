from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class TelexUser(BaseModel):
    id: str
    name: str


class TelexMessage(BaseModel):
    id: str
    type: str
    channel_id: str
    from_user: TelexUser = Field(..., alias="from")
    text: str
    metadata: Optional[Dict[str, Any]] = None
