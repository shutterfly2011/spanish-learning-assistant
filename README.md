# Spanish Learning Assistant

A web-based Spanish vocabulary learning tool powered by LLMs. Enter Spanish words to get detailed analyses including meanings, conjugations, etymology, cognates, and example sentences.

## Features

- **Word Analysis**: Enter any Spanish word to get:
  - Meaning and word type (verb, noun, adjective, etc.)
  - Verb conjugations (present, preterite, imperfect, future, subjunctive)
  - Etymology and origin
  - English cognates (words with the same root)
  - Similar-looking words (to avoid confusion)
  - Example sentences with translations
  - CEFR difficulty level

- **Conversation Practice**: Have free-form conversations in Spanish with grammar corrections

- **Vocabulary Tracking**: Session-based tracking of words you've looked up

- **Configurable LLM Backend**:
  - Ollama (local/network LLM server)
  - Amazon Bedrock (Claude models)

## Quick Start

### Using Docker (Recommended)

1. Clone or download this repository

2. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

3. Edit `.env` with your settings:
   ```bash
   # For Ollama (default)
   LLM_PROVIDER=ollama
   OLLAMA_BASE_URL=http://host.docker.internal:11434
   OLLAMA_MODEL=llama3

   # For Bedrock (optional)
   # LLM_PROVIDER=bedrock
   # AWS_ACCESS_KEY_ID=your-key
   # AWS_SECRET_ACCESS_KEY=your-secret
   ```

4. Start the application:
   ```bash
   docker-compose up --build
   ```

5. Open http://localhost:8501 in your browser

### Running Locally

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set environment variables or create a `config.yaml` file

4. Run the app:
   ```bash
   cd src
   streamlit run app.py
   ```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM backend: `ollama` or `bedrock` | `ollama` |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama model name | `llama3` |
| `AWS_ACCESS_KEY_ID` | AWS access key (for Bedrock) | - |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key (for Bedrock) | - |
| `AWS_REGION` | AWS region | `us-east-1` |
| `BEDROCK_MODEL_ID` | Bedrock model ID | `anthropic.claude-3-sonnet-20240229-v1:0` |

### UI Settings

Click the **Settings** button in the app to configure:
- LLM provider and model
- Ollama server URL
- Bedrock model ID and region
- CEFR level filter (A1-C2)

Settings changed in the UI persist for the session only.

## Usage Examples

### Word Lookup

Type a Spanish word to get a detailed analysis:

```
hablar
```

The assistant will provide:
- Meaning: "to speak, to talk"
- Conjugation table for all major tenses
- Etymology: From Latin "fabulare"
- English cognates: fable, fabulous
- Similar words: halar (to pull), hallar (to find)
- Example sentences

### Conversation Practice

Type a Spanish sentence or greeting to start a conversation:

```
Hola, como estas?
```

The assistant will respond in Spanish and help correct any mistakes.

### Questions About Spanish

Ask questions in English:

```
What's the difference between ser and estar?
```

## Project Structure

```
spanish-learning-assistant/
├── src/
│   ├── app.py              # Main Streamlit application
│   ├── config.py           # Configuration management
│   ├── session_state.py    # Session state management
│   ├── components/
│   │   ├── chat.py         # Chat interface
│   │   ├── settings.py     # Settings dialog
│   │   └── vocabulary.py   # Vocabulary tracker sidebar
│   ├── llm/
│   │   ├── base.py         # Abstract LLM interface
│   │   ├── ollama_client.py
│   │   └── bedrock_client.py
│   └── prompts/
│       └── spanish_tutor.py # System prompts
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Supported Ollama Models

Any model available on your Ollama server can be used. Recommended models:
- `llama3` - Good general performance
- `mistral` - Fast and capable
- Custom fine-tuned models

## Supported Bedrock Models

Claude models available on Amazon Bedrock:
- `anthropic.claude-3-sonnet-20240229-v1:0`
- `anthropic.claude-3-haiku-20240307-v1:0`
- `anthropic.claude-3-opus-20240229-v1:0`

## License

MIT License
