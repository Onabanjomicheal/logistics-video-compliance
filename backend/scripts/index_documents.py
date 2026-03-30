import os
import glob
import logging
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv(override=True)

# document loaders andd spllitters
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# azure components import
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch

# setup logging
logging.basicConfig(
    level = logging.INFO,
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("Indexer")

def index_docs():
    """
    Reads the PDFs, chunks and uploads them to Azure Search (vector store)
    """

    # defines paths, we look for data folder
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.abspath(os.path.join(current_dir, "..", "data"))

    # check the environment variables
    logger.info("="*60)
    logger.info("Environment Configuration Check")
    logger.info(f"AZURE_OPENAI_ENDPOINT : {os.getenv('AZURE_OPENAI_ENDPOINT')}")
    logger.info(f"AZURE_OPENAI_API_VERSION : {os.getenv('AZURE_OPENAI_API_VERSION')}")
    logger.info(
        "Embedding Deployment : "
        f"{os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT', 'text-embedding-3-small')}"
    )
    logger.info(f"AZURE_SEARCH_ENDPOINT : {os.getenv('AZURE_SEARCH_ENDPOINT')}")
    logger.info(f"AZURE_SEARCH_INDEX_NAME : {os.getenv('AZURE_SEARCH_INDEX_NAME')}")
    logger.info("="*60)

    # validate required environment variables
    required_env_vars = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_SEARCH_ENDPOINT",
        "AZURE_SEARCH_API_KEY",
        "AZURE_SEARCH_INDEX_NAME"
    ]

    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        logger.error("Please check your .env file and ensure all the variables are set ")
        return

    # initialize the embedding model : turns text into vectors
    try:
        logger.info("Initializing Azure Open AI Embeddings........")
        embeddings = AzureOpenAIEmbeddings(
            azure_deployment=os.getenv(
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"
            ),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01"),
        )

        logger.info("Embeddings model initialized successfully.")

    except Exception as e:
        logger.error(f"Failed to initialize embeddings: {e}")
        logger.error(f"Please verify Azure OpenAI deployment name and endpoint.")
        return

    # initialize the Azure Search
    try:
        logger.info("Initializing Azure Search Vector Store........")
        index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")
        vector_store = AzureSearch(
            azure_search_endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
            azure_search_key=os.getenv("AZURE_SEARCH_API_KEY"),
            index_name=index_name,
            embedding_function=embeddings.embed_query,
        )

        logger.info(f"Vector Store initialized for index : {index_name}")

    except Exception as e:
        logger.error(f"Failed to initialize Azure Search: {e}")
        logger.error(f"Please verify Azure Search endpoint, API key and index name.")
        return

    # Find PDF and HTML files
    pdf_files = glob.glob(os.path.join(data_dir, "*.pdf"))
    html_files = glob.glob(os.path.join(data_dir, "*.html"))
    if not pdf_files and not html_files:
        logger.warning(f"No PDFs or HTML files found in {data_dir}. Please add files.")
        return
    logger.info(
        f"Found {len(pdf_files)} PDFs and {len(html_files)} HTML files to process."
    )

    all_splits = []

    # process each pdf
    for pdf_path in pdf_files:
        try:
            logger.info(f"Loading: {os.path.basename(pdf_path)}......")
            loader = PyPDFLoader(pdf_path)
            raw_docs =  loader.load()

            # chunking strategy
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size = 1000,
                chunk_overlap = 200
            )
            splits = text_splitter.split_documents(raw_docs)
            for split in splits:
                split.metadata["source"] = os.path.basename(pdf_path)

            all_splits.extend(splits)
            logger.info(f"Split into {len(splits)} chunks.")
            
        except Exception as e:
            logger.error(f"Failed to  process {pdf_path}: {e}")

    # process each html
    for html_path in html_files:
        try:
            logger.info(f"Loading: {os.path.basename(html_path)}......")
            with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
                text = soup.get_text(separator=" ")
                raw_docs = [Document(page_content=text, metadata={"source": os.path.basename(html_path)})]

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )
            splits = text_splitter.split_documents(raw_docs)
            all_splits.extend(splits)
            logger.info(f"Split into {len(splits)} chunks.")
        except Exception as e:
            logger.error(f"Failed to process {html_path}: {e}")

    # Upload to Azure
    if all_splits:
        logger.info(
            f"Uploading {len(all_splits)} chunks to Azure Search index : {index_name}........"
        )
        try:
            # azure search accepts batches automatically via this method
            vector_store.add_documents(documents=all_splits)
            logger.info("=" * 60)
            logger.info("Indexing Complete! Knowledge Base is ready....")
            logger.info(f"Total chunks indexed : {len(all_splits)}")
            logger.info("=" * 60)
        except Exception as e:
            logger.error(f"Failed to upload the documents to Azure Search : {e}")
            logger.error("Please check the Azure Search configuration and try again")
    else:
        logger.warning("No documents were processed.")

if __name__ == "__main__":
    index_docs()
