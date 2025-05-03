# filename: auto_search_crawl4ai_fastapi.py

import sys
import asyncio
from fastapi import FastAPI
from pydantic import BaseModel
from duckduckgo_search import DDGS
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.content_filter_strategy import BM25ContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from test2 import process_prompt

from fastapi.middleware.cors import CORSMiddleware

# - Windows subprocess fix ---
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# --- FastAPI app setup ---
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ✅ Allow any origin
    allow_credentials=True,
    allow_methods=["*"],  # ✅ Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # ✅ Allow all headers
)
# --
# --- Limit browsers with Semaphore ---
browser_semaphore = asyncio.Semaphore(2)

# --- Request model ---
class PromptRequest(BaseModel):
    prompt: str


# --- Step 3: FastAPI endpoint ---
@app.post("/crawl_prompt")
async def crawl_from_prompt(request: PromptRequest):
    answer = await process_prompt(request.prompt)
    return {"answer": answer}

# --- Run server directly ---
if __name__ == "__main__":
    import uvicorn

    config = uvicorn.Config(
        "test2:app",    # your filename: app
        host="127.0.0.2",
        port=8000,
        workers=1,              # Very important for Playwright
        loop="asyncio",
        timeout_keep_alive=5,
        log_level="info"
    )
    server = uvicorn.Server(config)
    server.run()
