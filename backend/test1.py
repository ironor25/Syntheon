import sys
import asyncio

if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
import asyncio
import os
import tempfile
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

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

system_prompt = """
You are an AI assistant tasked with providing detailed answers based solely on the given context.
Your goal is to analyze the information provided and formulate a comprehensive, well-structured response to the question.

Context will be passed as "Context:"
User question will be passed as "Question:"

To answer the question:
1. Thoroughly analyze the context, identifying key information relevant to the question.
2. Organize your thoughts and plan your response to ensure a logical flow of information.
3. Formulate a detailed answer that directly addresses the question, using only the information provided in the context.
4. When the context supports an answer, ensure your response is clear, concise, and directly addresses the question.
5. When there is no context, just say you have no context and stop immediately.
6. If the context doesn't contain sufficient information to fully answer the question, state this clearly in your response.
7. Avoid explaining why you cannot answer or speculating about missing details. Simply state that you lack sufficient context when necessary.

Format your response as follows:
1. Use clear, concise language.
2. Organize your answer into paragraphs for readability.
3. Use bullet points or numbered lists where appropriate to break down complex information.
4. If relevant, include any headings or subheadings to structure your response.
5. Ensure proper grammar, punctuation, and spelling throughout your answer.
6. Do not mention what you received in context, just focus on answering based on the context.

Important: Base your entire response solely on the information provided in the context. Do not include any external knowledge or assumptions not present in the given text.
"""


def call_llm(prompt: str, context: str | None = None):
    """Calls the LLM model with the given prompt and optional context.

    Args:
        prompt (str): The user prompt/question to send to the LLM
        with_context (bool, optional): Whether to include system context. Defaults to True.
        context (str | None, optional): Additional context to provide to the LLM. Defaults to None.

    Yields:
        str: Generated text chunks from the LLM response stream

    Returns:
        Generator[str, None, None]: A generator yielding response chunks
    """
    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": f"Context: {context}, Question: {prompt}",
        },
    ]

   
    response = ollama.chat(model="llama3.2:latest", stream=True, messages=messages)
    # print(response)
    for chunk in response:
        if chunk["done"] is False:
            yield chunk["message"]["content"]
        else:
            break


def get_vector_collection() -> tuple[chromadb.Collection, chromadb.Client]:
    """Creates or retrieves a vector collection for storing embeddings.

    Creates an embedding function using Ollama and initializes a persistent ChromaDB client.
    Returns both the collection and client objects.

    Returns:
        tuple[chromadb.Collection, chromadb.Client]: A tuple containing:
            - The ChromaDB collection for storing embeddings
            - The ChromaDB client instance
    """
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
    """Normalizes a URL by removing common prefixes and replacing special characters.

    Args:
        url (str): The URL to normalize.

    Returns:
        str: The normalized URL with https://, www. removed and /, -, . replaced with underscores.

    Example:
        >>> normalize_url("https://www.example.com/path")
        "example_com_path"
    """
    normalized_url = (
        url.replace("https://", "")
        .replace("www.", "")
        .replace("/", "_")
        .replace("-", "_")
        .replace(".", "_")
    )
    # print("Normalized URL", normalized_url)
    return normalized_url


def add_to_vector_database(results: list[CrawlResult]):
    """Adds crawl results to a vector database for semantic search.

    Takes a list of crawl results, processes the markdown content by splitting it into chunks,
    and stores the chunks in a ChromaDB vector collection with associated metadata.

    Args:
        results (list[CrawlResult]): List of crawl results containing markdown content and URLs

    Returns:
        None

    Note:
        - Uses RecursiveCharacterTextSplitter to split markdown into chunks
        - Creates temporary markdown files for processing
        - Normalizes URLs for use as document IDs
        - Upserts documents, metadata and IDs to ChromaDB collection
    """
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
        # print(markdown_result)
        temp_file.write(markdown_result)
        temp_file.flush()
        temp_file.close()

        loader = UnstructuredMarkdownLoader(temp_file.name, mode="single")
        docs = loader.load()
        all_splits = text_splitter.split_documents(docs)
        os.unlink(temp_file.name)  # Delete the temporary file

        normalized_url = normalize_url(result.url)

        if all_splits:
            for idx, split in enumerate(all_splits):
                documents.append(split.page_content)
                metadatas.append({"source": result.url})
                ids.append(f"{normalized_url}_{idx}")

            print("Upsert collection: ", id(collection))
            collection.upsert(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )

async def crawl_webpage(urls: list[str],prompt:str):
    bm25_filter = BM25ContentFilter(user_query=prompt,bm25_threshold=1.2)
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
        page_timeout=20000,  # in ms: 20 seconds
    )
    browser_config = BrowserConfig(headless=True, text_mode=True, light_mode=True)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        results = await crawler.arun_many(urls, config=crawler_config)
        return results

async def get_urls(search_term:str,num_result:int = 10):
    try:
        discard_urls = ["youtube.com", "britannica.com", "vimeo.com"]
        # search_term ="What is llm?"
        for url in discard_urls:
            search_term += f" -site:{url}"

        results = DDGS().text(search_term, max_results=10)
        results = [result["href"] for result in results]
        return results

    except Exception as e:
        error_msg = ("❌ Failed to fetch results from the web", str(e))
        print(error_msg)
        return error_msg
  

async def main(prompt):


    # collection,chroma_client = get_vector_collection()
            web_urls = await get_urls(search_term= prompt)
            print(web_urls)
            collection, chroma_client = get_vector_collection()
            if not web_urls:
                print("no results")
            results = await crawl_webpage(urls=web_urls,prompt=prompt)
            add_to_vector_database(results)
            qresults = collection.query(query_texts=[prompt], n_results=10)
            context = qresults.get("documents")[0]

            chroma_client.delete_collection(
                name="web_llm"
            )  # Delete collection after use

            llm_response = call_llm(
                context=context, prompt=prompt
            )
            answer = ""
            for chunk in llm_response:
                answer +=  chunk
            print(answer)
            return answer


if __name__ == "__main__":
    asyncio.run(main("what is a super computer"))
