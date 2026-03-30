import os
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch


class RulesRetriever:
    def __init__(self):
        self.search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.search_key = os.getenv("AZURE_SEARCH_API_KEY")
        self.index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION")

        if not all([self.search_endpoint, self.search_key, self.index_name, self.api_version]):
            raise RuntimeError("Azure Search/OpenAI embedding config missing.")

        self.embeddings = AzureOpenAIEmbeddings(
            azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"),
            openai_api_version=self.api_version,
        )
        self.vector_store = AzureSearch(
            azure_search_endpoint=self.search_endpoint,
            azure_search_key=self.search_key,
            index_name=self.index_name,
            embedding_function=self.embeddings.embed_query,
        )

    def retrieve(self, query_text, k=4):
        docs = self.vector_store.similarity_search(query_text, k=k)
        rules_text = "\n\n".join([d.page_content for d in docs])
        sources = [d.metadata.get("source", "") for d in docs]
        return rules_text, sources
