# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install Node.js
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean

WORKDIR /app

# Copy requirements and install backend dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy frontend package.json and install frontend dependencies
COPY frontend/package*.json ./frontend/
RUN cd frontend && npm install

# Copy the rest of the application
COPY . .

# Build frontend static files
RUN cd frontend && npm run build

# Set environment variables for demo mode
ENV DEMO_MODE=True

# Expose FastAPI port
EXPOSE 8000

# Run FastAPI serving both API and static frontend
# (Note: In a real production setup, we would mount the frontend/dist to FastAPI static files.
# For demo purposes, we will assume FastAPI serves the React app or they are run concurrently).
CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
