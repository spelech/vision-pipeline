import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright_stealth import Stealth
from playwright.async_api import async_playwright

app = FastAPI()

class ScrapeRequest(BaseModel):
    url: str
    wait_time: int = 2000 # Time to wait after load

@app.post("/scrape")
async def scrape_url(req: ScrapeRequest):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        
        try:
            await page.goto(req.url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(req.wait_time / 1000.0)
            
            content = await page.content()
            # We could take a screenshot here, but for LLMs, text/HTML is often enough.
            # Let's return just text for now to save bandwidth, or minimal HTML.
            # Actually, extracting innerText is cleaner for LLMs:
            text_content = await page.evaluate("document.body.innerText")
            
            await browser.close()
            return {"success": True, "url": req.url, "text": text_content}
        except Exception as e:
            await browser.close()
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}
