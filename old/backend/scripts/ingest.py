"""Corpus ingestion CLI: CSV -> embeddings -> Qdrant.

Usage (in a Python 3.12 venv with a real .env):
    python -m scripts.ingest --csv data/flipkart_product_review.csv

Uses the configured backend/embedding (real bge via HF). Idempotency / blue-green
re-index is hardened in Step 15; this is the straightforward ingest path.
"""
from __future__ import annotations

import argparse

from app.observability.logger import configure_logging, get_logger
from app.rag.data_converter import DataConverter
from app.rag.factory import build_vector_store_provider

logger = get_logger(__name__)


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Ingest product reviews into the vector store.")
    parser.add_argument("--csv", default="data/flipkart_product_review.csv")
    args = parser.parse_args()

    docs = DataConverter(args.csv).convert()
    logger.info("loaded_documents", extra={"count": len(docs)})

    provider = build_vector_store_provider()
    provider.add_documents(docs)
    logger.info("ingestion_complete", extra={"count": len(docs)})


if __name__ == "__main__":
    main()
