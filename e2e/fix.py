import re

with open("e2e/ingestion.spec.ts", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("await page.locator('input[type=\"file\"]').first()", "await page.locator('input[accept=\"image/*\"]')")

with open("e2e/ingestion.spec.ts", "w", encoding="utf-8") as f:
    f.write(text)
