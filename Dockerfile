# Use a slim Python base image
FROM python:3.11-slim

# Set environment variables for Java and Python
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
ENV PATH="$JAVA_HOME/bin:$PATH"

# Install system dependencies required by PySpark and Cartopy
RUN apt-get update && apt-get install -y \
    openjdk-21-jre-headless \
    libgeos-dev \
    libproj-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY analysis.py .
COPY visualize.py .
COPY main.py .

# Create results directory
RUN mkdir -p results

# Run the orchestrator when the container launches
CMD ["python", "main.py"]