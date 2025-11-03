from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from src.routes import movies


# Initialize the main FastAPI app
app = FastAPI(
    title="Movie Theater API",
    description="API for managing a movie theater, built with FastAPI.",
    version="1.0.0"
)

# =============================================================================
# Custom Exception Handler (Fixes 422 -> 400 Requirement)
# =============================================================================


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Catches Pydantic's RequestValidationError and returns a 400 Bad Request
    with the required detail message.
    """
    return JSONResponse(
        status_code=400,
        content={"detail": "Invalid input data."},
    )
app.include_router(movies.router)
