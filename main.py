from fastapi import FastAPI
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the app
app = FastAPI()

# Log on startup
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 FastAPI app has started.")

# Simple GET route
@app.get("/hello")
async def hello():
    return {"message": "Hello, world!"}
