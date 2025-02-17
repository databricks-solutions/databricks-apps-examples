import logging
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from typing import Annotated
import os
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from load_tester import router as load_test_router
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
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


SERVING_ENDPOINT_NAME = os.getenv("SERVING_ENDPOINT_NAME")

if not SERVING_ENDPOINT_NAME:
    logger.error("SERVING_ENDPOINT_NAME environment variable is not set")
    raise ValueError("SERVING_ENDPOINT_NAME environment variable is not set")

# client
def client():
    return WorkspaceClient()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    content: str


@api_app.post("/chat", response_model=ChatResponse)
def chat_with_llm(
    request: ChatRequest, client: Annotated[WorkspaceClient, Depends(client)]
):
    response = client.serving_endpoints.query(
        SERVING_ENDPOINT_NAME,
        messages=[ChatMessage(content=request.message, role=ChatMessageRole.USER)],
    )
    return ChatResponse(content=response.choices[0].message.content)
    
@api_app.get("/")
async def root():
    return {"message": "Hello World"}

api_app.include_router(load_test_router)

