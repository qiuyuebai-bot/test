import chromadb
from chromadb.config import Settings

# Chroma 0.4.x replaced the legacy Settings(chroma_db_impl=...) constructor
# with PersistentClient.  Request telemetry disabled so this smoke test stays
# deterministic in offline/development environments (older clients may still
# print non-fatal telemetry warnings).
client = chromadb.PersistentClient(
    path="./chroma_data",
    settings=Settings(anonymized_telemetry=False),
)
collection = client.get_or_create_collection(name="test")
collection.upsert(
    documents=["Test document content"],
    metadatas=[{"source": "test"}],
    ids=["1"],
)
results = collection.query(query_texts=["Test"], n_results=1)
print("Chroma works correctly:", results)
