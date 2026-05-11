# BuenoSpanish MCP Server

A Model Context Protocol (MCP) server that provides Spanish word lookup functionality using the BuenoSpanish dictionary website. This server exposes tools for looking up Spanish words, getting meanings, etymology, and related words.

## Features

- **Word Lookup**: Get comprehensive information about Spanish words
- **Structured Data**: Access meanings, examples, and etymology as structured data
- **MCP Protocol**: Full MCP server with HTTP streaming support
- **Docker Ready**: Easily deployable as a container

## Available Tools

### `lookup_word`
Look up a Spanish word and return detailed information including meanings, etymology, and related words.

**Parameters:**
- `word` (string): The Spanish word to look up

**Returns:** Formatted string with complete word information

### `get_word_meanings`
Get the meanings of a Spanish word as structured data.

**Parameters:**
- `word` (string): The Spanish word to look up

**Returns:** List of dictionaries with definition, Spanish example, and English example

### `get_etymology`
Get the etymology of a Spanish word.

**Parameters:**
- `word` (string): The Spanish word to look up

**Returns:** Etymology information as a string

### `get_related_words`
Get related Spanish and English words for a given Spanish word.

**Parameters:**
- `word` (string): The Spanish word to look up

**Returns:** Dictionary with related Spanish words, related English words, and English cognates

## Quick Start

### Using Docker (Recommended)

1. Build and run the MCP server:
   ```bash
   cd buenospanish_mcp
   docker-compose up --build
   ```

2. The server will be available at `http://localhost:8000`

### Running Locally

1. Install dependencies:
   ```bash
   cd buenospanish_mcp
   pip install -r requirements.txt
   ```

2. Run the server:
   ```bash
   python mcp_server.py
   ```

## Testing the Server

### Using MCP Client

You can test the server using any MCP-compatible client. Here's an example using a simple Python client:

```python
import requests

# Test the lookup_word tool
response = requests.post("http://localhost:8000/tools/lookup_word", json={
    "word": "hola"
})
print(response.json())
```

### Using the Test Script

A test script is provided to verify the server functionality:

```bash
cd buenospanish_mcp
python test_server.py
```

This script will:
- Check server health
- Test all available tools
- Display sample results

### Manual Testing with curl

Test the server health:
```bash
curl http://localhost:8000/health
```

Test a word lookup:
```bash
curl -X POST http://localhost:8000/tools/lookup_word \
  -H "Content-Type: application/json" \
  -d '{"word": "casa"}'
```

### Example Output

For the word "casa" (house), you might get:

```
=== casa ===
Smart definition: Casa means house, home.

Meanings:
  1. house, home
     ES: Mi casa es grande.
     EN: My house is big.

Etymology: From Latin "casa" meaning hut or cottage.

Related Spanish: hogar (hearth), vivienda (dwelling)
Related English: 'case', 'cash', 'chase'
English cognates: case
```

## Configuration

### Environment Variables

- `MCP_SERVER_PORT`: Port to run the server on (default: 8000)

### Docker Configuration

The server runs on port 8000 inside the container. Use docker-compose to easily configure the port mapping:

```yaml
services:
  mcp-server:
    build: .
    ports:
      - "8080:8000"  # Map host port 8080 to container port 8000
```

### Deploying to a Remote Docker Host

If you want to deploy the MCP server to a remote host with Docker installed, follow these steps:

1. Copy the `buenospanish_mcp` folder to the remote machine. For example:
   ```bash
   scp -r buenospanish_mcp user@remote-host:/home/user/
   ```

2. SSH into the remote host:
   ```bash
   ssh user@remote-host
   ```

3. Go to the project folder and build/start the service:
   ```bash
   cd /home/user/buenospanish_mcp
   docker-compose up --build -d
   ```

4. Confirm the container is running:
   ```bash
   docker ps | grep mcp-server
   ```

5. Access the service from your local machine using the remote host address and exposed port:
   ```bash
   curl http://remote-host:8000/health
   ```

> If your remote host is behind a firewall or cloud security group, make sure port `8000` is open for inbound traffic.

## Architecture

The server uses:
- **FastMCP**: Pythonic MCP server framework
- **HTTP Streaming**: Streamable HTTP transport for real-time communication
- **BeautifulSoup**: HTML parsing for the BuenoSpanish website
- **Requests**: HTTP client for web scraping

## Development

### Project Structure

```
buenospanish_mcp/
├── mcp_server.py      # Main MCP server implementation
├── test_server.py     # Test script for server functionality
├── requirements.txt    # Python dependencies
├── Dockerfile         # Docker container definition
├── docker-compose.yml # Docker Compose configuration
└── README.md          # This file
```

### Adding New Tools

To add new tools, decorate functions with `@app.tool()` and provide proper type hints and docstrings:

```python
@app.tool()
def my_new_tool(param: str) -> dict:
    """Description of what the tool does.

    Args:
        param: Description of the parameter

    Returns:
        Description of the return value
    """
    # Implementation here
    pass
```

## Troubleshooting

### Server Won't Start

- Check that port 8000 is not already in use
- Ensure all dependencies are installed
- Check Docker logs: `docker-compose logs mcp-server`

### Word Lookup Fails

- Verify internet connectivity
- Check that the BuenoSpanish website is accessible
- Some words may not exist in the dictionary

### Connection Issues

- Ensure the server is running and accessible
- Check firewall settings
- Verify the correct URL and port

## License

This project uses data from BuenoSpanish.com. Please respect their terms of service and usage policies.