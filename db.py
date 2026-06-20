import os
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

# Load configurations from your .env file
load_dotenv()

try:
    # Initialize a global Threaded Connection Pool
    # minconn=1: Keeps at least 1 connection open at all times
    # maxconn=10: Allows the pool to grow up to 10 concurrent connections under high traffic
    db_pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT")
    )
    print("PostgreSQL Threaded Connection Pool initialized successfully.")
except Exception as e:
    print(f"Failed to initialize database connection pool: {e}")
    db_pool = None

@contextmanager
def get_db():
    """
    Context manager to safely borrow a connection from the pool
    and guarantee it returns to the pool even if errors occur.
    """
    if db_pool is None:
        raise RuntimeError("Database connection pool is not initialized.")
        
    # Borrow a connection from the pool
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        # This always executes, ensuring the connection is returned to the pool
        db_pool.putconn(conn)