FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create reports directory
RUN mkdir -p /app/reports

# Environment — override these at runtime.
# The LLM runs on the host's Ollama; from inside Docker use host.docker.internal.
ENV OLLAMA_HOST="http://host.docker.internal:11434"
ENV THINKMCP_MODEL="qwen3:8b"
ENV TAVILY_API_KEY=""
ENV GITHUB_TOKEN=""
ENV THINKMCP_REPORTS_DIR="/app/reports"
ENV THINKMCP_MEMORY_DB="/app/thinkmcp_memory.db"

# Streamlit UI on 8501
EXPOSE 8501

# MCP HTTP server on 8000 (used when running as a remote MCP server)
EXPOSE 8000

# Default command: Streamlit UI
# Override with: docker run ... python -m transport.http_transport --port 8000
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
