"""CSV -> LangChain Document conversion.

Ported verbatim in behavior from the demo's ``flipkart/data_converter.py``; only the
import path changes. Quality/structure changes happen in later steps, not here
(Step 1 preserves parity).
"""
from __future__ import annotations

import pandas as pd
from langchain_core.documents import Document

from app.core.guardrails import neutralize_injection


class DataConverter:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def convert(self) -> list[Document]:
        df = pd.read_csv(self.file_path)[["product_title", "review"]]
        # Reviews are untrusted UGC -> neutralize prompt-injection at ingestion (D18) so
        # stored/retrieved content is data, not commands.
        return [
            Document(
                page_content=neutralize_injection(str(row["review"])),
                metadata={"product_name": row["product_title"]},
            )
            for _, row in df.iterrows()
        ]
