import os
from dotenv import load_dotenv

load_dotenv()

required = [
    "AZURE_VISION_ENDPOINT",
    "AZURE_VISION_KEY",
    "AZURE_OPENAI_CHAT_DEPLOYMENT",
    "AZURE_OPENAI_API_VERSION",
    "AZURE_SEARCH_ENDPOINT",
    "AZURE_SEARCH_API_KEY",
    "AZURE_SEARCH_INDEX_NAME",
]

missing = [k for k in required if not os.getenv(k)]
if missing:
    print("Missing required env vars:")
    for k in missing:
        print(f" - {k}")
else:
    print("All required env vars are set for Vision + RAG.")
