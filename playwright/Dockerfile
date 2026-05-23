FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

RUN pip install fastapi uvicorn playwright-stealth

COPY main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
