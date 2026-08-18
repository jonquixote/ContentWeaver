import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# src/models/* are Flask-SQLAlchemy declarative models bound to `db.metadata`.
# FastAPI runs sync dependencies and sync handlers in separate threadpool
# threads, so Flask-SQLAlchemy's scoped `db.session` (keyed by the app context
# of the calling thread) breaks across the dependency/handler boundary. Instead
# bind a plain engine + sessionmaker to the same DATABASE_URL; the existing
# models work with it in any thread, and db.metadata still drives create_all.
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'sqlite:///' + os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'database', 'app.db')))

engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
_session_factory = sessionmaker(bind=engine)


@contextmanager
def db_session():
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()


def get_db():
    with db_session() as session:
        yield session