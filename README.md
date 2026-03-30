## Compliance QA Pipeline

End-to-end real-time compliance auditing for logistics video streams using Azure AI Vision, Azure OpenAI, and Azure AI Search. Exposes a FastAPI API and a CLI runner.

### What It Does
- Samples frames from a live stream (RTSP/USB/video file)
- Uses Azure AI Vision to describe the scene + OCR
- Retrieves relevant regulations from Azure AI Search (RAG)
- Runs compliance audit using Azure OpenAI

### Requirements
- Python 3.13+
- Azure resources configured (Video Indexer, OpenAI, Search, Monitor)

### Setup
1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   uv sync
   ```
3. Configure environment:
   - Copy `.env` values from your Azure resources.
   - Do not commit secrets.

### Run the API
```bash
uv run uvicorn backend.src.api.server:app
```

### Run the CLI
```bash
uv run python main.py
```

### Run Tests
```bash
uv run pytest
```

### Environment Variables
Required:
- `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`
- `AZURE_VISION_ENDPOINT`, `AZURE_VISION_KEY`
- `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_CHAT_DEPLOYMENT`
- `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`
- `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_API_KEY`, `AZURE_SEARCH_INDEX_NAME`
- `APPLICATION_INSIGHTS_CONNECTION_STRING`

Optional:
- `OTEL_SERVICE_NAME`
- `OTEL_TRACES_SAMPLER`, `OTEL_TRACES_SAMPLER_ARG`
- `VI_CONNECT_TIMEOUT`, `VI_READ_TIMEOUT`
- `AZURE_VISION_API_VERSION`

### Troubleshooting
**Azure Vision errors:**
- Ensure `AZURE_VISION_ENDPOINT` and `AZURE_VISION_KEY` are set.
- Check the API version if you see 404 or unsupported features.

**Application Map missing links:**
- Run without `--reload`
- Ensure Application Insights connection string is set
```bash
uv run uvicorn backend.src.api.server:app
```
