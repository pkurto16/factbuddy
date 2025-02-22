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
        self.context_window: List[str] = []
        self.max_context_items = 5

    async def analyze_context(self, statement: str) -> str:
        """Analyze statement in context of previous statements"""
        self.context_window.append(statement)
        if len(self.context_window) > self.max_context_items:
            self.context_window.pop(0)

        context_prompt = "\n".join(self.context_window)

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a fact-checking assistant. Analyze the statement in context and provide a clear, factual version of the claim being made."},
                {"role": "user", "content": f"Context:\n{context_prompt}\n\nLatest statement:\n{statement}\n\nExtract the main factual claim from this statement, considering the context."}
            ]
        )

        return response.choices[0].message.content

    async def generate_search_query(self, claim: str) -> str:
        """Generate an effective search query for the claim"""
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Generate a precise search query to fact-check this claim."},
                {"role": "user", "content": f"Claim: {claim}"}
            ]
        )

        return response.choices[0].message.content

    async def scrape_url(self, session: aiohttp.ClientSession, url: str) -> Dict[str, Any]:
        """Scrape and extract content from a URL"""
        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Remove script and style elements
                    for script in soup(["script", "style"]):
                        script.decompose()

                    # Extract text
                    text = soup.get_text(separator=' ', strip=True)

                    return {
                        "url": url,
                        "content": text[:5000],  # Limit content length
                        "status": "success"
                    }
                return {"url": url, "content": "", "status": "error"}
        except Exception as e:
            return {"url": url, "content": "", "status": "error", "error": str(e)}

    async def search_and_scrape(self, query: str) -> List[Dict[str, Any]]:
        """Perform search and parallel scraping of results"""
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

    async def analyze_source_credibility(self, source: Dict[str, Any], claim: str) -> Dict[str, Any]:
        """Analyze credibility of a source regarding the claim"""
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Analyze this source's credibility and its stance on the claim. Provide a credibility score (0-100) and explanation."},
                {"role": "user", "content": f"Claim: {claim}\n\nSource content: {source['content']}\nURL: {source['url']}"}
            ]
        )

        analysis = response.choices[0].message.content

        # Extract score using a simple pattern (improve this based on your needs)
        try:
            score = float(analysis.split("Score:")[1].split("\n")[0].strip())
        except:
            score = 50.0  # Default score if parsing fails

        return {
            **source,
            "credibility_score": score,
            "analysis": analysis
        }

    async def synthesize_final_check(self, claim: str, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Synthesize final fact-check result"""
        # Sort sources by credibility
        sorted_sources = sorted(sources, key=lambda x: x["credibility_score"], reverse=True)
        top_sources = sorted_sources[:3]

        sources_text = "\n\n".join([
            f"Source {i+1} (Credibility: {s['credibility_score']}):\n{s['content'][:500]}..."
            for i, s in enumerate(top_sources)
        ])

        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Synthesize a final fact-check result based on the most credible sources."},
                {"role": "user", "content": f"Claim: {claim}\n\nSources:\n{sources_text}"}
            ]
        )

        synthesis = response.choices[0].message.content

        # Calculate overall credibility score
        overall_score = np.mean([s["credibility_score"] for s in top_sources])

        return {
            "type": "factCheck",
            "statement": claim,
            "truthScore": float(overall_score),
            "correction": synthesis,
            "sources": [{"url": s["url"], "credibility": s["credibility_score"]} for s in top_sources],
            "timestamp": datetime.now().isoformat()
        }

    async def stream_fact_check(self, statement: str, websocket) -> None:
        """Stream fact-checking process results"""
        try:
            # 1. Context Analysis
            await websocket.send_json({
                "type": "status",
                "message": "Analyzing context...",
                "phase": "context",
                "progress": 0
            })

            contextualized_claim = await self.analyze_context(statement)

            # Send contextualized claim
            await websocket.send_json({
                "type": "analysis",
                "source": "Context Analysis",
                "credibility": 100,
                "summary": f"Analyzed claim: {contextualized_claim}"
            })

            # 2. Search Query Generation
            await websocket.send_json({
                "type": "status",
                "message": "Generating search query...",
                "phase": "search",
                "progress": 20
            })

            search_query = await self.generate_search_query(contextualized_claim)

            # Send search query
            await websocket.send_json({
                "type": "search",
                "query": search_query,
                "sources": []
            })

            # 3. Web Scraping
            await websocket.send_json({
                "type": "status",
                "message": "Gathering sources...",
                "phase": "sources",
                "progress": 40
            })

            sources = await self.search_and_scrape(search_query)

            # Update with found sources
            await websocket.send_json({
                "type": "search",
                "query": search_query,
                "sources": [s["url"] for s in sources]
            })

            # 4. Source Analysis
            await websocket.send_json({
                "type": "status",
                "message": "Analyzing sources...",
                "phase": "analysis",
                "progress": 60
            })

            # Analyze sources one by one and stream results
            analyzed_sources = []
            for i, source in enumerate(sources):
                analysis = await self.analyze_source_credibility(source, contextualized_claim)
                analyzed_sources.append(analysis)

                # Send individual source analysis
                await websocket.send_json({
                    "type": "analysis",
                    "source": source["url"],
                    "credibility": analysis["credibility_score"],
                    "summary": analysis["analysis"]
                })

                # Update progress
                await websocket.send_json({
                    "type": "status",
                    "message": f"Analyzing source {i + 1} of {len(sources)}...",
                    "phase": "analysis",
                    "progress": 60 + (20 * (i + 1) / len(sources))
                })

            # 5. Final Synthesis
            await websocket.send_json({
                "type": "status",
                "message": "Synthesizing results...",
                "phase": "synthesis",
                "progress": 90
            })

            final_result = await self.synthesize_final_check(
                contextualized_claim,
                analyzed_sources
            )

            # Send completion status
            await websocket.send_json({
                "type": "status",
                "message": "Fact-check complete",
                "phase": "complete",
                "progress": 100
            })

            # Send final result
            await websocket.send_json(final_result)

        except Exception as e:
            print(f"Error in fact-checking: {str(e)}")  # Server-side logging
            await websocket.send_json({
                "type": "error",
                "message": f"Error during fact-checking: {str(e)}"
            })