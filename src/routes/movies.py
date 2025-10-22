import math
from typing import List, Type

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload, QueryableAttribute

# Make sure this import is correct (from the previous step)
from database import get_db
from database.models import (
    MovieModel,
    GenreModel,
    ActorModel,
    CountryModel,
    LanguageModel,
)
from schemas.movies import (
    MoviesListResponse,
    MovieCreateRequest,
    MovieDetailResponse,
    MovieUpdateRequest,
    MovieUpdateResponse,
)

router = APIRouter()


# --- Helper Functions ---

async def get_or_create_related_instance(
    db: AsyncSession, model: Type, name: str
) -> Type:
    """
    Retrieves a related entity (Genre, Actor, Language) by name,
    or creates it if it doesn't exist.
    """
    query = select(model).where(model.name == name)
    result = await db.execute(query)
    instance = result.scalar_one_or_none()

    if not instance:
        instance = model(name=name)
        db.add(instance)
        await db.flush()  # Flush to get the ID without committing
    return instance


async def get_movie_by_id(movie_id: int, db: AsyncSession) -> MovieModel | None:
    """
    Retrieves a single movie by its ID, eagerly loading all
    related entities for a detailed response.
    """
    query = (
        select(MovieModel)
        .where(MovieModel.id == movie_id)
        .options(
            joinedload(MovieModel.country),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.actors),
            selectinload(MovieModel.languages),
        )
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


# --- Task 1: Implement Movies List Endpoint ---

@router.get(
    "/movies/",
    response_model=MoviesListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_movies_list(
    request: Request,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=10, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves a paginated list of movies, sorted by ID in descending order.
    """
    offset = (page - 1) * per_page

    # Query for the total count of movies
    total_query = select(func.count(MovieModel.id))
    total_result = await db.execute(total_query)
    total_items = total_result.scalar_one()

    if not total_items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No movies found."
        )

    total_pages = math.ceil(total_items / per_page)

    # Query for the paginated list of movies
    movies_query = (
        select(MovieModel)
        .order_by(MovieModel.id.desc())
        .offset(offset)
        .limit(per_page)
    )
    movies_result = await db.execute(movies_query)
    movies = movies_result.scalars().all()

    if not movies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No movies found."
        )

    # Build pagination URLs
    # This URL path needs to match the test client's request path
    base_url = "/api/v1/theater/movies/"  # <-- FIX: Trailing space removed
    prev_page = (
        f"{base_url}?page={page - 1}&per_page={per_page}" if page > 1 else None
    )
    next_page = (
        f"{base_url}?page={page + 1}&per_page={per_page}"
        if page < total_pages
        else None
    )

    # <-- FIX: This line (132) is now completely empty, no spaces
    return MoviesListResponse(
        movies=movies,
        prev_page=prev_page,
        next_page=next_page,
        total_pages=total_pages,
        total_items=total_items,
    )


# --- Task 2: Implement Movie Creation Endpoint ---

@router.post(
    "/movies/",
    response_model=MovieDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_movie(
    movie_data: MovieCreateRequest, db: AsyncSession = Depends(get_db)
):
    """
    Creates a new movie in the database, including its related entities.
    """
    # Check for duplicates
    duplicate_query = select(MovieModel).where(
        and_(
            MovieModel.name == movie_data.name,
            MovieModel.date == movie_data.date
        )
    )
    duplicate_result = await db.execute(duplicate_query)
    if duplicate_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A movie with the name '{movie_data.name}' and "
                   f"release date '{movie_data.date}' already exists.",
        )

    # Get or create Country
    country_query = select(CountryModel).where(
        CountryModel.code == movie_data.country
    )
    country_result = await db.execute(country_query)
    country = country_result.scalar_one_or_none()
    if not country:
        # <-- FIX: Two spaces added before the '#'
        country = CountryModel(code=movie_data.country, name=None)  # Added name=None for clarity
        db.add(country)
        await db.flush()

    # Get or create Genres, Actors, and Languages
    genres_list = [
        await get_or_create_related_instance(db, GenreModel, name)
        for name in movie_data.genres
    ]
    actors_list = [
        await get_or_create_related_instance(db, ActorModel, name)
        for name in movie_data.actors
    ]
    languages_list = [
        await get_or_create_related_instance(db, LanguageModel, name)
        for name in movie_data.languages
    ]

    # Create new MovieModel instance
    new_movie = MovieModel(
        name=movie_data.name,
        date=movie_data.date,
        score=movie_data.score,
        overview=movie_data.overview,
        status=movie_data.status.value,  # Use the enum's value
        budget=movie_data.budget,
        revenue=movie_data.revenue,
        country=country,
        genres=genres_list,
        actors=actors_list,
        languages=languages_list,
    )

    db.add(new_movie)
    await db.commit()
    await db.refresh(new_movie)

    # Re-fetch the movie with all relationships loaded for the response
    created_movie = await get_movie_by_id(new_movie.id, db)
    return created_movie


# --- Task 3: Implement Movie Details Endpoint ---

@router.get(
    "/movies/{movie_id}/",
    response_model=MovieDetailResponse,
    status_code=status.HTTP_200_OK,
)
async def get_movie_details(movie_id: int, db: AsyncSession = Depends(get_db)):
    """
    Retrieves detailed information for a single movie by its ID.
    """
    movie = await get_movie_by_id(movie_id, db)

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with the given ID was not found.",
        )
    return movie


# --- Task 4: Implement Movie Deletion Endpoint ---

@router.delete(
    "/movies/{movie_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    """
    Deletes a specific movie by its ID.
    """
    # Fetch the movie to ensure it exists before deleting
    query = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(query)
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with the given ID was not found.",
        )

    await db.delete(movie)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Task 5: Implement Movie Update Endpoint ---

@router.patch(
    "/movies/{movie_id}/",
    response_model=MovieUpdateResponse,
    status_code=status.HTTP_200_OK,
)
async def update_movie(
    movie_id: int,
    movie_data: MovieUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Partially updates a specific movie's details by its ID.
    """
    # Fetch the movie
    query = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(query)
    movie = result.scalar_one_or_none()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with the given ID was not found.",
        )

    # Get update data, excluding fields that were not provided
    update_data = movie_data.model_dump(exclude_unset=True)

    # Handle enum conversion if status is provided
    if "status" in update_data and update_data["status"]:
        update_data["status"] = update_data["status"].value

    # Apply updates
    for key, value in update_data.items():
        setattr(movie, key, value)

    await db.commit()

    return MovieUpdateResponse(detail="Movie updated successfully.")
