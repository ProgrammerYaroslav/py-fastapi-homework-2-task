import math
from typing import List, Type

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import func, exc

# Import database session, models, and schemas
from database.session_postgresql import get_db
from database.models import (
    MovieModel,
    CountryModel,
    GenreModel,
    ActorModel,
    LanguageModel,
)
from schemas.movies import (
    PaginatedMovieResponse,
    MovieBriefResponse,
    MovieDetailResponse,
    MovieCreateRequest,
    MovieUpdateRequest,
    MessageResponse,
)

router = APIRouter(prefix="/movies", tags=["Movies"])

# =============================================================================
# Helper Functions
# =============================================================================

async def _get_or_create_country(code: str, db: AsyncSession) -> CountryModel:
    """
    Retrieve a country by its code, or create it if it doesn't exist.
    """
    query = select(CountryModel).where(CountryModel.code == code)
    result = await db.execute(query)
    country = result.scalar_one_or_none()
    
    if not country:
        country = CountryModel(code=code, name=None)  # Name can be populated later
        db.add(country)
        await db.flush()  # Flush to get the ID before commit
        await db.refresh(country)
    return country


async def _get_or_create_related_list(
    names: List[str], 
    model: Type[GenreModel] | Type[ActorModel] | Type[LanguageModel], 
    db: AsyncSession
) -> List[GenreModel | ActorModel | LanguageModel]:
    """
    Generic helper to get or create related entities (Genres, Actors, Languages).
    """
    objects = []
    
    # First, find existing objects
    existing_query = select(model).where(model.name.in_(names))
    existing_result = await db.execute(existing_query)
    existing_map = {obj.name: obj for obj in existing_result.scalars()}
    
    for name in names:
        if name in existing_map:
            objects.append(existing_map[name])
        else:
            # Create new one if it doesn't exist
            new_obj = model(name=name)
            db.add(new_obj)
            objects.append(new_obj)
            
    # Flush to get IDs for new objects
    if len(objects) > len(existing_map):
        await db.flush()
        for obj in objects:
            if not obj.id:
                await db.refresh(obj)
                
    return objects


async def _get_movie_details_by_id(movie_id: int, db: AsyncSession) -> MovieModel:
    """
    Retrieve a single movie by ID with all relationships eagerly loaded.
    Raises 404 if not found.
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
    movie = result.scalar_one_or_none()
    
    if not movie:
        raise HTTPException(
            status_code=404, 
            detail="Movie with the given ID was not found."
        )
    return movie


# =============================================================================
# Endpoint Implementations
# =============================================================================

@router.get(
    "/",
    response_model=PaginatedMovieResponse,
    summary="Get Paginated List of Movies"
)
async def get_movies(
    request: Request,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number to retrieve"),
    per_page: int = Query(10, ge=1, le=20, description="Items per page"),
):
    """
    Task 1: Implement Movies List Endpoint
    Retrieves a paginated list of movies, sorted by ID in descending order.
    """
    offset = (page - 1) * per_page
    
    # Query for total items
    count_query = select(func.count(MovieModel.id))
    total_items = (await db.execute(count_query)).scalar_one()
    
    if total_items == 0:
        raise HTTPException(status_code=404, detail="No movies found.")
        
    total_pages = math.ceil(total_items / per_page)
    
    if page > total_pages:
        raise HTTPException(status_code=404, detail="No movies found.")

    # Query for the paginated movies
    movies_query = (
        select(MovieModel)
        .order_by(MovieModel.id.desc())
        .offset(offset)
        .limit(per_page)
    )
    movies_result = await db.execute(movies_query)
    movies = movies_result.scalars().all()

    # --- FIX: Hard-code base URL to match /theater/movies/ requirement ---
    base_url = "/theater/movies/"

    # Build next and previous page URLs
    next_page = (
        f"{base_url}?page={page + 1}&per_page={per_page}"
        if page < total_pages
        else None
    )
    prev_page = (
        f"{base_url}?page={page - 1}&per_page={per_page}"
        if page > 1
        else None
    )

    return PaginatedMovieResponse(
        movies=[MovieBriefResponse.model_validate(m) for m in movies],
        prev_page=prev_page,
        next_page=next_page,
        total_pages=total_pages,
        total_items=total_items,
    )


@router.post(
    "/",
    response_model=MovieDetailResponse,
    status_code=201,
    summary="Create a New Movie",
    # --- NOTE: 400 response is now handled by the custom exception handler ---
)
async def create_movie(
    movie_data: MovieCreateRequest, 
    db: AsyncSession = Depends(get_db)
):
    """
    Task 2: Implement Movie Creation Endpoint
    Creates a new movie and links/creates related entities.
    """
    # Check for duplicates
    duplicate_query = select(MovieModel).where(
        MovieModel.name == movie_data.name, 
        MovieModel.date == movie_data.date
    )
    existing_movie = (await db.execute(duplicate_query)).scalar_one_or_none()
    
    if existing_movie:
        raise HTTPException(
            status_code=409,
            detail=f"A movie with the name '{movie_data.name}' and release date '{movie_data.date}' already exists."
        )

    try:
        # Handle related entities
        country = await _get_or_create_country(movie_data.country, db)
        genres = await _get_or_create_related_list(movie_data.genres, GenreModel, db)
        actors = await _get_or_create_related_list(movie_data.actors, ActorModel, db)
        languages = await _get_or_create_related_list(movie_data.languages, LanguageModel, db)

        # Create the new movie
        new_movie = MovieModel(
            **movie_data.model_dump(
                exclude={'country', 'genres', 'actors', 'languages'}
            )
        )
        
        # Link related objects
        new_movie.country = country
        new_movie.genres = genres
        new_movie.actors = actors
        new_movie.languages = languages
        
        db.add(new_movie)
        await db.commit()
        
        # Retrieve the full, detailed object for the response
        return await _get_movie_details_by_id(new_movie.id, db)

    except exc.IntegrityError:
        # --- FIX: Changed detail message to required string ---
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")
    except Exception as e:
        await db.rollback()
        # Fallback for other unexpected errors
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


@router.get(
    "/{movie_id}/",
    response_model=MovieDetailResponse,
    summary="Get Movie Details by ID"
)
async def get_movie_details(
    movie_id: int, 
    db: AsyncSession = Depends(get_db)
):
    """
    Task 3: Implement Movie Details Endpoint
    Retrieves detailed information for a single movie by its ID.
    """
    # The helper function handles the query and 404 logic
    movie = await _get_movie_details_by_id(movie_id, db)
    return movie


@router.delete(
    "/{movie_id}/",
    status_code=204,
    summary="Delete a Movie by ID"
)
async def delete_movie(
    movie_id: int, 
    db: AsyncSession = Depends(get_db)
):
    """
    Task 4: Implement Movie Deletion Endpoint
    Deletes a movie by its ID.
    """
    # Use db.get for a simple primary key lookup
    movie = await db.get(MovieModel, movie_id)
    
    if not movie:
        raise HTTPException(
            status_code=404, 
            detail="Movie with the given ID was not found."
        )
        
    await db.delete(movie)
    await db.commit()
    
    return Response(status_code=204)


@router.patch(
    "/{movie_id}/",
    response_model=MessageResponse,
    summary="Update Movie Details by ID",
    # --- NOTE: 400 response is now handled by the custom exception handler ---
)
async def update_movie(
    movie_id: int,
    movie_data: MovieUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Task 5: Implement Movie Update Endpoint
    Updates a movie's details. Only updates fields provided in the request.
    """
    # Use db.get for a simple primary key lookup
    movie = await db.get(MovieModel, movie_id)
    
    if not movie:
        raise HTTPException(
            status_code=404, 
            detail="Movie with the given ID was not found."
        )

    # Get update data, excluding fields that were not set in the request
    update_data = movie_data.model_dump(exclude_unset=True)

    if not update_data:
        # If no data is provided, it's a successful "no-op"
        return MessageResponse(detail="Movie updated successfully.")

    # Apply updates
    for key, value in update_data.items():
        setattr(movie, key, value)
        
    try:
        await db.commit()
        await db.refresh(movie)
    except exc.IntegrityError:
        # --- FIX: Changed detail message to required string ---
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

    return MessageResponse(detail="Movie updated successfully.")
