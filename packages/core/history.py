"""Per-user chat history in DynamoDB single-table (Decision 1).

Isolation is structural: the partition key embeds the user id, so user A's query can never
return user B's messages. This replaces the demo's process-global in-memory dict (which
leaked across users and was lost on restart).

Item shape (single-table):
    PK = "USER#{user_id}#SESSION#{session_id}"
    SK = "MSG#{nanos}#{rand}"   (sortable -> chronological)
    role, content
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from core.config import Settings, get_settings


def _partition_key(user_id: str, session_id: str) -> str:
    return f"USER#{user_id}#SESSION#{session_id}"


class DynamoChatHistory:
    """DynamoDB-backed chat history with per-user isolation."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._table_name = self._settings.dynamodb_table
        self._resource: Any = boto3.resource(
            "dynamodb",
            endpoint_url=self._settings.dynamodb_endpoint or None,
            region_name=self._settings.aws_region,
            aws_access_key_id=self._settings.aws_access_key_id or "local",
            aws_secret_access_key=self._settings.aws_secret_access_key or "local",
        )

    def _table(self) -> Any:
        return self._resource.Table(self._table_name)

    def ensure_table(self) -> None:
        """Create the single table if it doesn't exist (idempotent; for local/dev)."""
        client = self._resource.meta.client
        if self._table_name in client.list_tables()["TableNames"]:
            return
        client.create_table(
            TableName=self._table_name,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        client.get_waiter("table_exists").wait(TableName=self._table_name)

    def add_message(self, user_id: str, session_id: str, role: str, content: str) -> None:
        sort_key = f"MSG#{time.time_ns()}#{uuid.uuid4().hex[:8]}"
        self._table().put_item(
            Item={
                "PK": _partition_key(user_id, session_id),
                "SK": sort_key,
                "role": role,
                "content": content,
            }
        )

    def get_messages(self, user_id: str, session_id: str, limit: int = 20) -> list[BaseMessage]:
        response = self._table().query(
            KeyConditionExpression=Key("PK").eq(_partition_key(user_id, session_id)),
            ScanIndexForward=True,
            Limit=limit,
        )
        messages: list[BaseMessage] = []
        for item in response.get("Items", []):
            content = str(item.get("content", ""))
            if item.get("role") == "human":
                messages.append(HumanMessage(content=content))
            else:
                messages.append(AIMessage(content=content))
        return messages

    def clear(self, user_id: str, session_id: str) -> int:
        """Delete all messages for a (user, session). Returns count (GDPR path, Step 24)."""
        table = self._table()
        response = table.query(
            KeyConditionExpression=Key("PK").eq(_partition_key(user_id, session_id))
        )
        items = response.get("Items", [])
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
        return len(items)
