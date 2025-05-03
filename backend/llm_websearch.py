from fastapi import FastAPI
from crawl4ai import AsyncWebCrawler

app = FastAPI()

@app.get("/crawl")
async def crawl_url(url: str):
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)
        return {"markdown": result.markdown.fit_markdown}