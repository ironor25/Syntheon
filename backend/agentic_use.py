from langchain_ollama import ChatOllama
from browser_use import Agent
from pydantic import SecretStr
import asyncio

# Initialize the model
llm=ChatOllama(model="qwen2.5", num_ctx=32000)

# Create agent with the model
async def main():
    agent = Agent(
        task="compare deepseek and openai api pricing",
        llm=llm
    )
    result = await agent.run()
    print(result)

asyncio.run(main())