# pfastapiserver/main.py
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from router import router as auth_router  # Fixed filename typo from 'router' to 'routers'

app = FastAPI(
    title="My Systems Project Backend",
    description="FastAPI sandbox for working with Supabase and Postgres",
    version="1.0.0"
)

# --- THE 50ml BOTTLE MIDDLEWARE SYSTEM ---
CURRENT_ACTIVE_REQUESTS = 0
MAX_BOTTLE_CAPACITY = 50

@app.middleware("http")
async def limit_concurrency_middleware(request: Request, call_next):
    global CURRENT_ACTIVE_REQUESTS
    
    # Skip checking CORS preflight options so the browser connection doesn't drop
    if request.method == "OPTIONS":
        return await call_next(request)

    # If the bottle is full (we hit 50 concurrent requests), reject immediately
    if CURRENT_ACTIVE_REQUESTS >= MAX_BOTTLE_CAPACITY:
        return Response(
            content="Server bottle full! Request rejected to prevent crash.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
        
    # If there is room, increment the counter and let the request pass
    CURRENT_ACTIVE_REQUESTS += 1
    try:
        response = await call_next(request)
        return response
    finally:
        # Pours the slot back out of the bottle as soon as the execution finishes
        CURRENT_ACTIVE_REQUESTS -= 1


# Configure CORS so your React frontend (port 5173) can talk to this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://resonant-biscotti-de8ec7.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the routes routing module layout matrix
app.include_router(auth_router)

@app.get("/")
def read_root():
    return {"status": "healthy", "message": "Server routing backbone is fully initialized and protected."}