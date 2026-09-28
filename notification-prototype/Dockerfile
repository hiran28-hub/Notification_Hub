FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered output for live logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install project dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Ensure data directory exists inside container
RUN mkdir -p /app/data

EXPOSE 5000

# Start Flask application (listens on 0.0.0.0:5000)
CMD ["python", "app.py"]
