from fastapi import APIRouter
from app.schemas import SQLRequest
from app.inference_service import generate_sql_from_nl

router = APIRouter()

@router.post("/generate")
def generate_sql(request: SQLRequest):
    try:
        sql = generate_sql_from_nl(
            request.db_schema,
            request.question
        )

        return {
            "success": True,
            "generated_sql": sql
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
