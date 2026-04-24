FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: Run with web UI on port 8089
# Headless: docker compose run --rm loadtest locust -f locustfile.py --host=http://api:8000 -u 100 -r 10 --headless
CMD ["locust", "-f", "locustfile.py", "--host=http://api:8000", "--port=8089"]
