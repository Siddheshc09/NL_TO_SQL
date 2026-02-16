from pydantic import BaseModel
from typing import Dict, Any

class SQLRequest(BaseModel):
    db_schema: Dict[str, Any]
    question: str
