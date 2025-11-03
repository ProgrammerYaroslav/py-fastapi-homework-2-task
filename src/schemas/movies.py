import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, ConfigDict, model_validator

# =============================================================================
# Reusable Schemas for Related Models
# =============================================================================

class CountryResponse(BaseModel):
    """Schema for country details in a response."""
    id: int
    code: str
    name: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class GenreResponse(BaseModel):
    """Schema for genre details in a response."""
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class ActorResponse(BaseModel):
    """Schema for actor details in a response."""
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class LanguageResponse(BaseModel):
    """Schema for language details in a response."""
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    """A generic message response schema."""
    detail: str


# =============================================================================
# Schemas for Task 1: GET /movies/ (List Movies)
# =============================================================================

class MovieBriefResponse(BaseModel):
    """Schema for a single movie in a paginated list."""
    id: int
    name: str
    date: datetime.date
    score: float
    overview: str
    
    model_config = ConfigDict(from_attributes=True)


class PaginatedMovieResponse(BaseModel):
    """Schema for the paginated movie list response."""
    movies: List[MovieBriefResponse]
    prev_page: Optional[str] = None
    next_page: Optional[str] = None
    total_pages: int
    total_items: int


# =============================================================================
# Schemas for Task 2 (POST) & 3 (GET by ID)
# =============================================================================

class MovieDetailResponse(BaseModel):
    """Schema for the detailed movie response (used for create and get-by-id)."""
    id: int
    name: str
    date: datetime.date
    score: float
    overview: str
    status: str
    budget: float
    revenue: float
    country: CountryResponse
    genres: List[GenreResponse]
    actors: List[ActorResponse]
    languages: List[LanguageResponse]

    model_config = ConfigDict(from_attributes=True)


class MovieCreateRequest(BaseModel):
    """Schema for the movie creation request body."""
    name: str = Field(..., max_length=255)
    date: datetime.date
    score: float = Field(..., ge=0, le=100)
    overview: str
    status: Literal["Released", "Post Production", "In Production"]
    budget: float = Field(..., ge=0)
    revenue: float = Field(..., ge=0)
    country: str = Field(..., description="ISO 3166-1 alpha-3 code")
    genres: List[str]
    actors: List[str]
    languages: List[str]

    @model_validator(mode='after')
    def validate_date(self) -> 'MovieCreateRequest':
        """Validate that the movie date is not more than one year in the future."""
        if self.date > (datetime.date.today() + datetime.timedelta(days=365)):
            raise ValueError("Release date cannot be more than one year in the future")
        return self


# =============================================================================
# Schemas for Task 5: PATCH /movies/{movie_id} (Update Movie)
# =============================================================================

class MovieUpdateRequest(BaseModel):
    """Schema for the movie update request body (all fields optional)."""
    name: Optional[str] = Field(None, max_length=255)
    date: Optional[datetime.date] = None
    score: Optional[float] = Field(None, ge=0, le=100)
    overview: Optional[str] = None
    status: Optional[Literal["Released", "Post Production", "In Production"]] = None
    budget: Optional[float] = Field(None, ge=0)
    revenue: Optional[float] = Field(None, ge=0)
