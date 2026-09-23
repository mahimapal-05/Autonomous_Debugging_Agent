FROM python:3.11-slim

# Install system dependencies, OpenJDK 17 and Maven for Java debugging sandbox
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jdk \
    maven \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set Java environment variables
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose standard Streamlit port (Render dynamically overrides with $PORT)
EXPOSE 8501

# Streamlit run command with dynamic port assignment for Render compatibility
CMD ["sh", "-c", "python -m streamlit run frontend/streamlit_app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false"]
