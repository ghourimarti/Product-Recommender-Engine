import os

# Set required env vars before any app module is imported.
# pydantic-settings reads os.environ at import time.
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-minimum-32-characters!!")
os.environ.setdefault("GROQ_API_KEY", "gsk_test_placeholder_key")
os.environ.setdefault("CHROMA_PERSIST_DIR", "test_chroma_db")
