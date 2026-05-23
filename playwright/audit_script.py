import json
import asyncio
from playwright.async_api import async_playwright

async def run_layout_audit(url="http://vision-pipeline:8501"):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        # Set desktop viewport
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await page.goto(url)
        await asyncio.sleep(2) # Wait for Alpine.js
        
        # Inject and run audit
        audit_code = """
        () => {
            const elements = Array.from(document.querySelectorAll('body *:not(script):not(style)'))
                .filter(el => {
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && style.visibility !== 'hidden' && el.offsetWidth > 0;
                });
            const overlaps = [];
            for (let i = 0; i < elements.length; i++) {
                const elA = elements[i];
                const rectA = elA.getBoundingClientRect();
                for (let j = i + 1; j < elements.length; j++) {
                    const elB = elements[j];
                    const rectB = elB.getBoundingClientRect();
                    if (!(rectA.right < rectB.left || rectA.left > rectB.right || rectA.bottom < rectB.top || rectA.top > rectB.bottom)) {
                        if (elA.contains(elB) || elB.contains(elA)) continue;
                        if (rectA.width < 5 || rectB.width < 5) continue;
                        overlaps.push({
                            a: { tag: elA.tagName, id: elA.id, classes: elA.className, rect: rectA },
                            b: { tag: elB.tagName, id: elB.id, classes: elB.className, rect: rectB }
                        });
                    }
                }
            }
            return overlaps;
        }
        """
        overlaps = await page.evaluate(audit_code)
        await browser.close()
        return overlaps

if __name__ == "__main__":
    import sys
    # This would be triggered by me to "see" the current state
    res = asyncio.run(run_layout_audit())
    print(json.dumps(res, indent=2))
