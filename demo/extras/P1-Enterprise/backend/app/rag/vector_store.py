from langchain_chroma import Chroma
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import CharacterTextSplitter

from app.core.config import get_settings

settings = get_settings()

_retriever = None
_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def _get_embedding() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=_EMBEDDING_MODEL)


def build_vector_store(csv_path: str) -> None:
    """Ingest a CSV file and persist to ChromaDB. Run once via scripts/build_vector_store.py."""
    loader = CSVLoader(file_path=csv_path, encoding="utf-8")
    docs = loader.load()
    splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    texts = splitter.split_documents(docs)
    Chroma.from_documents(
        texts,
        _get_embedding(),
        persist_directory=settings.CHROMA_PERSIST_DIR,
    )


def get_retriever(k: int = 5):
    """Return a cached retriever instance. Thread-safe for read-only use after first call."""
    global _retriever
    if _retriever is None:
        db = Chroma(
            persist_directory=settings.CHROMA_PERSIST_DIR,
            embedding_function=_get_embedding(),
        )
        _retriever = db.as_retriever(search_kwargs={"k": k})
    return _retriever
