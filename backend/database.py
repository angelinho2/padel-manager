"""
database.py — Conexión a la base de datos

SQLModel usa SQLAlchemy por debajo. Aquí definimos:
  - el engine (la conexión a SQLite)
  - get_session() que FastAPI inyectará en cada endpoint como dependencia
"""
from sqlmodel import create_engine, Session
from config import settings

# create_engine crea la conexión a la BD.
# check_same_thread=False es necesario para SQLite cuando FastAPI
# maneja múltiples peticiones concurrentes en distintos hilos.
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # Si DEBUG=True, muestra cada query SQL en la consola
    connect_args={"check_same_thread": False},
)


def get_session():
    """
    Dependency de FastAPI.

    FastAPI llama a esta función automáticamente en cada endpoint que la
    declare como dependencia (Depends(get_session)).
    Crea una sesión de BD, la entrega al endpoint y la cierra al terminar,
    aunque se produzca un error.

    Uso en un endpoint:
        async def mi_endpoint(session: Session = Depends(get_session)):
            ...
    """
    with Session(engine) as session:
        yield session
