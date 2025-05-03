import sys
import asyncio
import os
import tempfile
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from crawl4ai.browser_manager import BrowserManager
import chromadb
import ollama
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
from crawl4ai.content_filter_strategy import BM25ContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.models import CrawlResult
from duckduckgo_search import DDGS
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

# --- Windows subprocess fix ---
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# --- FastAPI app setup ---
app = FastAPI()

# --- CORS middleware for cross-origin testing ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Constants ---
system_prompt = """
You are an AI assistant tasked with providing detailed answers based solely on the given context.
[...Your original system_prompt continues here...]
"""

# --- Models ---
class PromptRequest(BaseModel):
    prompt: str

# --- Functions ---
browser_semaphore = asyncio.Semaphore(1)  # Limit to 1 browser instance

def call_llm(prompt: str, context: str | None = None):
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context: {context}, Question: {prompt}"},
    ]
    response = ollama.chat(model="llama3.2:latest", stream=True, messages=messages)
    for chunk in response:
        if chunk["done"] is False:
            yield chunk["message"]["content"]
        else:
            break

def get_vector_collection():
    ollama_ef = OllamaEmbeddingFunction(
        url="http://localhost:11434/api/embeddings",
        model_name="nomic-embed-text:latest",
    )
    chroma_client = chromadb.PersistentClient(
        path="./web-search-llm-db", settings=Settings(anonymized_telemetry=False)
    )
    return (
        chroma_client.get_or_create_collection(
            name="web_llm",
            embedding_function=ollama_ef,
            metadata={"hnsw:space": "cosine"},
        ),
        chroma_client,
    )

def normalize_url(url):
    normalized_url = (
        url.replace("https://", "")
        .replace("www.", "")
        .replace("/", "_")
        .replace("-", "_")
        .replace(".", "_")
    )
    return normalized_url

def add_to_vector_database(results: list[CrawlResult]):
    collection, _ = get_vector_collection()

    for result in results:
        documents, metadatas, ids = [], [], []

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=400,
            chunk_overlap=100,
            separators=["\n\n", "\n", ".", "?", "!", " ", ""],
        )
        if result.markdown:
            markdown_result = result.markdown.fit_markdown
        else:
            continue

        temp_file = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8", dir=r"C:\tmp")
        temp_file.write(markdown_result)
        temp_file.flush()
        temp_file.close()

        loader = UnstructuredMarkdownLoader(temp_file.name, mode="single")
        docs = loader.load()
        all_splits = text_splitter.split_documents(docs)
        os.unlink(temp_file.name)

        normalized_url = normalize_url(result.url)

        if all_splits:
            for idx, split in enumerate(all_splits):
                documents.append(split.page_content)
                metadatas.append({"source": result.url})
                ids.append(f"{normalized_url}_{idx}")

            collection.upsert(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )

async def crawl_webpage(urls: list[str], prompt: str):
    bm25_filter = BM25ContentFilter(user_query=prompt, bm25_threshold=1.2)
    md_generator = DefaultMarkdownGenerator(content_filter=bm25_filter)

    crawler_config = CrawlerRunConfig(
        markdown_generator=md_generator,
        check_robots_txt=True,
        excluded_tags=["nav", "footer", "header", "form", "img", "a"],
        only_text=True,
        exclude_social_media_links=True,
        keep_data_attributes=False,
        cache_mode=CacheMode.BYPASS,
        remove_overlay_elements=True,
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
        page_timeout=60000,
    )
    browser_config = BrowserConfig(headless=False, text_mode=True, light_mode=True,browser_mode="builtin")

   
    async with AsyncWebCrawler(config=browser_config) as crawler:
        results = await crawler.arun_many(urls, config=crawler_config)
        print("✅ Crawling completed.")
        await crawler.close()
        print("✅ BrowserManager shutdown after crawling.")
        return results


    

        
    # browser_config
async def get_urls(search_term: str, num_result: int = 5):
    try:
        discard_urls = ["youtube.com", "britannica.com", "vimeo.com"]
        for url in discard_urls:
            search_term += f" -site:{url}"

        results = DDGS().text(search_term, max_results=num_result)
        return [result["href"] for result in results if "href" in result]

    except Exception as e:
        print("❌ Failed to fetch results from the web", str(e))
        return []

async def process_prompt(prompt: str):
    web_urls = await get_urls(search_term=prompt)
    if not web_urls:
        return "❌ No results found."

    collection, chroma_client = get_vector_collection()

    results = await crawl_webpage(urls=web_urls, prompt=prompt)
    add_to_vector_database(results)

    qresults = collection.query(query_texts=[prompt], n_results=10)
    context = qresults.get("documents")[0]

    chroma_client.delete_collection(name="web_llm")

    llm_response = call_llm(context=context, prompt=prompt)
    answer = ""
    for chunk in llm_response:
        answer += chunk
    return answer

# --- FastAPI endpoint ---
@app.post("/crawl_prompt")
async def crawl_from_prompt(request: PromptRequest):
    
    return {"answer": await process_prompt(request.prompt)}

# --- Run server if file is executed ---
if __name__ == "__main__":
    import uvicorn

    config = uvicorn.Config(
        "test2:app",    # your filename: app
        host="127.0.0.1",
        port=8000,
        workers=1,              # Very important for Playwright
        loop="asyncio",
        timeout_keep_alive=5,
        log_level="info"
    )
    server = uvicorn.Server(config)
    server.run()

