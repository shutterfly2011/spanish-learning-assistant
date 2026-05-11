FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY mcp_server.py .

# Expose MCP server port
EXPOSE 8000

# Health check
HEALTHCHECK CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

# Run MCP server
CMD ["python", "mcp_server.py"]