# KelasYar – production image
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    asyncpg psycopg2-binary uvicorn[standard]

COPY . .

RUN mkdir -p uploads

# runs migrations then starts API + bot
CMD ["sh", "-c", "alembic upgrade head && python run.py --no-migrate"]
