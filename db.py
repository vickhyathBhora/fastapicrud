import os
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

# Load local configurations from a .env file if it exists
load_dotenv()

db_pool = None

try:
    # Look for Render's unified master connection string
    database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        print("Production environment detected. Connecting to Render Cloud PostgreSQL...")
        db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=database_url,
            sslmode="require"  # 🌟 Mandatory for Render DB cloud transit security
        )
    else:
        print("Local environment detected. Connecting to local machine PostgreSQL...")
        db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "pcrud_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT", "5432")
            # Local development usually doesn't enforce strict SSL encryption
        )
        
    print("PostgreSQL Threaded Connection Pool initialized successfully.")
except Exception as e:
    print(f"CRITICAL: Failed to initialize database connection pool: {e}")
    db_pool = None


@contextmanager
def get_db():
    """
    Context manager to safely borrow a connection from the pool
    and guarantee its safe return even if errors or exceptions occur.
    """
    if db_pool is None:
        raise RuntimeError("Database connection pool is offline or not initialized.")
        
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        # This always executes, putting the connection back into the pool
        db_pool.putconn(conn)