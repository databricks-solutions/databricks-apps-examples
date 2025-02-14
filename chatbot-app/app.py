import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from load_tester import router as load_test_router

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Logger initialized successfully!")

app = FastAPI()
ui_app = StaticFiles(directory="client/build", html=True)
api_app = FastAPI()

app.mount("/api", api_app)
app.mount("/", ui_app)

origins = [
    "http://localhost:3000",
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


SERVING_ENDPOINT_NAME = os.getenv("SERVING_ENDPOINT_NAME")

if not SERVING_ENDPOINT_NAME:
    logger.error("SERVING_ENDPOINT_NAME environment variable is not set")
    raise ValueError("SERVING_ENDPOINT_NAME environment variable is not set")


class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    content: str


@api_app.post("/chat", response_model=ChatResponse)
async def chat_with_llm(request: ChatRequest):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('DATABRICKS_TOKEN')}"
    }
    payload = {
        "messages": [{"role": "user", "content": request.message}]
    }
    async with httpx.AsyncClient() as client:
        try:
            request_url = f"https://{os.getenv('DATABRICKS_HOST')}/serving-endpoints/{SERVING_ENDPOINT_NAME}/invocations"
            response = await client.post(request_url, json=payload, headers=headers, timeout=500.0)
            response.raise_for_status()
            response_data = response.json()
            content = response_data['choices'][0]['message']['content']
            return ChatResponse(content=content)
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/")
async def root():
    return {"message": "Hello World"}

api_app.include_router(load_test_router)

