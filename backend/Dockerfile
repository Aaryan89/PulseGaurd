FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend and data directories
COPY backend/ ./backend/
COPY data/ ./data/

# Expose port
EXPOSE 8000

# Set Python path to include /app so it can resolve backend.* and data.* modules
ENV PYTHONPATH=/app

# Run uvicorn
CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
