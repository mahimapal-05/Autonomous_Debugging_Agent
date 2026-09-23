FROM python:3.11-slim

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Fix Debian-slim missing man pages dir and install Java JDK, Maven, Git, and build tools
RUN mkdir -p /usr/share/man/man1 /usr/share/man/man2 /usr/share/man/man7 \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       default-jdk-headless \
       maven \
       curl \
       git \
       gcc \
       python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set Java environment variables
ENV JAVA_HOME=/usr/lib/jvm/default-java
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
