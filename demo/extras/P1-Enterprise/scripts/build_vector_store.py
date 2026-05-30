"""
One-time script to ingest anime CSV data and build the ChromaDB vector store.

Usage:
    cd backend
    python ../scripts/build_vector_store.py --csv ../data/anime_updated.csv

Run this once before starting the backend. The vector store is persisted
to the path defined by CHROMA_PERSIST_DIR in your .env file.
"""
import argparse
import sys
from pathlib import Path

# Add backend to path so app imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.rag.vector_store import build_vector_store  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ChromaDB vector store from anime CSV")
    parser.add_argument(
        "--csv",
        required=True,
        help="Path to the anime CSV file (e.g. data/anime_updated.csv)",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv).resolve()
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)

    print(f"Building vector store from: {csv_path}")
    build_vector_store(str(csv_path))
    print("Vector store built successfully.")
    print("You can now start the backend server.")


if __name__ == "__main__":
    main()
