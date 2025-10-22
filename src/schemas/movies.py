import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, field_validator, confloat, constr
from typing import List, Optional


class MovieStatusEnum(str, Enum):
    """Enumeration for movie production statuses."""
    RELEASED = "Released"
    POST_PRODUCTION = "Post Production"
    IN_PRODUCTION = "In Production"


class MovieShortResponse(BaseModel):
    """Schema for a movie item in a paginated list."""
    id: int
    name: str
    date: datetime.date
    score: float
    overview: str

    model_config = ConfigDict(from_attributes=True)


class MoviesListResponse(BaseModel):
    """Schema for the paginated list of movies response."""
    movies: List[MovieShortResponse]
    prev_page: Optional[str] = None
    next_page: Optional[str] = None
    total_pages: int
    total_items: int


class CountrySchema(BaseModel):
    id: int
    code: str
    name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class GenreSchema(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class ActorSchema(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class LanguageSchema(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class MovieCreateRequest(BaseModel):
    name: constr(max_length=255)
    date: datetime.date
    score: confloat(ge=0, le=100)
    overview: str
    status: MovieStatusEnum
    budget: confloat(ge=0)
    revenue: confloat(ge=0)
    country: str  # ISO 3166-1 alpha-3 code
    genres: List[str]
    actors: List[str]
    languages: List[str]

    @field_validator('date')
    @classmethod
    def validate_date(cls, v: datetime.date) -> datetime.date:
        """Validate that the date is not more than one year in the future."""
        if v > datetime.date.today() + datetime.timedelta(days=365):
            raise ValueError("Date cannot be more than one year in the future")
        return v


class MovieDetailResponse(BaseModel):
    id: int
    name: str
    date: datetime.date
    score: float
    overview: str
    status: str
    budget: float
    revenue: float
    country: CountrySchema
    genres: List[GenreSchema]
    actors: List[ActorSchema]
    languages: List[LanguageSchema]

    model_config = ConfigDict(from_attributes=True)


class MovieUpdateRequest(BaseModel):
    name: Optional[constr(max_length=255)] = None
    date: Optional[datetime.date] = None
    score: Optional[confloat(ge=0, le=100)] = None
    overview: Optional[str] = None
    status: Optional[MovieStatusEnum] = None
    budget: Optional[confloat(ge=0)] = None
    revenue: Optional[confloat(ge=0)] = None


class MovieUpdateResponse(BaseModel):
    detail: str = "Movie updated successfully."
