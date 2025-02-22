from typing import List, Dict, Any
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from openai import AsyncOpenAI
import numpy as np
from urllib.parse import quote_plus
import json
from datetime import datetime

class FactCheckAgent:
    def __init__(self, openai_api_key: str):
        self.client = AsyncOpenAI(api_key=openai_api_key)

    async def generate_search_query(self, claim: str) -> str:
        """Generate an effective search query for the claim."""
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Generate a precise search query to fact-check this claim."},
                {"role": "user", "content": f"Claim: {claim}"}
            ]
        )
        return response.choices[0].message.content

    async def scrape_url(self, session: aiohttp.ClientSession, url: str) -> Dict[str, Any]:
        """Scrape and extract content from a URL."""
        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Remove script and style elements
                    for script in soup(["script", "style"]):
                        script.decompose()

                    # Extract text (limit to the first 5000 characters)
                    text = soup.get_text(separator=' ', strip=True)
                    return {
                        "url": url,
                        "content": text[:5000],
                        "status": "success"
                    }
                return {"url": url, "content": "", "status": "error"}
        except Exception as e:
            return {"url": url, "content": "", "status": "error", "error": str(e)}

    async def search_and_scrape(self, query: str) -> List[Dict[str, Any]]:
        """Perform search and parallel scraping of results."""
        search_url = f"https://www.google.com/search?q={quote_plus(query)}"

        async with aiohttp.ClientSession() as session:
            async with session.get(search_url) as response:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                # Extract URLs (adjust selectors based on Google's HTML structure)
                urls = [a['href'] for a in soup.select('a[href^="http"]')][:10]

                # Parallel scraping
                tasks = [self.scrape_url(session, url) for url in urls]
                results = await asyncio.gather(*tasks)

                return [r for r in results if r["status"] == "success"]

    async def synthesize_final_check(self, claim: str, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Synthesize a final fact-check result by summarizing the scraped sources and
        determining if the overall sentiment supports the claim.
        """
        sources_text = "\n\n".join([
            f"Source {i+1}: {s['content'][:500]}..."
            for i, s in enumerate(sources)
        ])
        prompt = (
            f"Claim: {claim}\n\n"
            f"Scraped Sources:\n{sources_text}\n\n"
            "Summarize the main points from the above sources and determine if the overall sentiment of the sources supports the claim. "
            "Respond with a brief summary and then conclude with either 'Supports' or 'Does not support' along with a short explanation."
        )
        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a fact-checking assistant that only summarizes scraped source content and determines whether the sentiment supports the given claim."
                },
                {"role": "user", "content": prompt}
            ]
        )

        synthesis = response.choices[0].message.content

        return {
            "type": "factCheck",
            "statement": claim,
            "correction": synthesis,
            "sources": [{"url": s["url"]} for s in sources],
            "timestamp": datetime.now().isoformat()
        }

    async def stream_fact_check(self, statement: str, websocket) -> None:
        """Stream fact-checking process results."""
        try:
            await websocket.send_json({
                "type": "status",
                "message": "Generating search query...",
                "phase": "search",
                "progress": 20
            })

            search_query = await self.generate_search_query(statement)

            await websocket.send_json({
                "type": "search",
                "query": search_query,
                "sources": []
            })

            await websocket.send_json({
                "type": "status",
                "message": "Scraping sources...",
                "phase": "sources",
                "progress": 40
            })

            sources = await self.search_and_scrape(search_query)

            await websocket.send_json({
                "type": "status",
                "message": f"Scraped {len(sources)} sources.",
                "phase": "sources",
                "progress": 60
            })

            final_result = await self.synthesize_final_check(statement, sources)

            await websocket.send_json({
                "type": "status",
                "message": "Fact-check complete",
                "phase": "complete",
                "progress": 100
            })

            await websocket.send_json(final_result)
        except Exception as e:
            print(f"Error in fact-checking: {str(e)}")
            await websocket.send_json({
                "type": "error",
                "message": f"Error during fact-checking: {str(e)}"
            })