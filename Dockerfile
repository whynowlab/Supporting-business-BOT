FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY .env.example .

# Create volume mount point for SQLite if needed, but usually handled by compose
# We need to make sure the data persists.

CMD ["python", "-m", "src.main"]
