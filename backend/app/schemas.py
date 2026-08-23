from typing import Any, Optional

from pydantic import BaseModel


class JobOut(BaseModel):
    id: str
    status: str  # queued | started | finished | failed
    job_type: str  # hmm | structure
    result: Optional[Any] = None
    error: Optional[str] = None
