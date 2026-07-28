"""Per-user chat history in DynamoDB single-table, with GDPR deletion/export.

Isolation is structural: the partition key is the user id, so user A's query can never return
user B's messages. All of a user's data lives under one partition, which makes account-level
right-to-be-forgotten (delete) and DSAR (export) a single query — no GSI or scan needed.

Item shape (single-table):
    PK = "USER#{user_id}"
    SK = "SESSION#{session_id}#MSG#{nanos}#{rand}"   (sortable -> chronological within a session)
    role, content
"""

from __future__ import annotations

import contextlib
import time
import uuid
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from core.config import Settings, get_settings


def _user_pk(user_id: str) -> str:
    return f"USER#{user_id}"


def _session_prefix(session_id: str) -> str:
    return f"SESSION#{session_id}#MSG#"


def _session_of(sort_key: str) -> str:
    # "SESSION#{sid}#MSG#..." -> sid
    return sort_key.split("#", 2)[1] if sort_key.startswith("SESSION#") else ""


class DynamoChatHistory:
    """DynamoDB-backed chat history with per-user isolation + GDPR delete/export."""

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
        # Enable TTL so the `ttl` attribute written by add_message actually expires items.
        # (Terraform sets this for the real table; local/dev needs it too or retention is inert.)
        with contextlib.suppress(Exception):  # not supported by every DynamoDB-local build
            client.update_time_to_live(
                TableName=self._table_name,
                TimeToLiveSpecification={"Enabled": True, "AttributeName": "ttl"},
            )

    def add_message(self, user_id: str, session_id: str, role: str, content: str) -> None:
        sort_key = f"{_session_prefix(session_id)}{time.time_ns()}#{uuid.uuid4().hex[:8]}"
        self._table().put_item(
            Item={
                "PK": _user_pk(user_id),
                "SK": sort_key,
                "role": role,
                "content": content,
                # Retention: DynamoDB TTL only expires items that carry a ttl attribute. The
                # table has TTL configured in Terraform, but nothing expires unless we write
                # this field. Epoch seconds; DynamoDB deletes the item some time after it passes.
                "ttl": int(time.time()) + self._settings.chat_retention_days * 86400,
            }
        )

    def get_messages(self, user_id: str, session_id: str, limit: int = 20) -> list[BaseMessage]:
        response = self._table().query(
            KeyConditionExpression=(
                Key("PK").eq(_user_pk(user_id)) & Key("SK").begins_with(_session_prefix(session_id))
            ),
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

    def _delete_items(self, items: list[dict[str, Any]]) -> int:
        table = self._table()
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
        return len(items)

    def clear_session(self, user_id: str, session_id: str) -> int:
        """Delete one session's messages. Returns count."""
        response = self._table().query(
            KeyConditionExpression=(
                Key("PK").eq(_user_pk(user_id)) & Key("SK").begins_with(_session_prefix(session_id))
            )
        )
        return self._delete_items(response.get("Items", []))

    def delete_user(self, user_id: str) -> int:
        """Right-to-be-forgotten: delete all of a user's data. Returns count."""
        response = self._table().query(KeyConditionExpression=Key("PK").eq(_user_pk(user_id)))
        return self._delete_items(response.get("Items", []))

    def export_user(self, user_id: str) -> list[dict[str, str]]:
        """Export all of a user's stored messages as plain records (DSAR)."""
        response = self._table().query(KeyConditionExpression=Key("PK").eq(_user_pk(user_id)))
        return [
            {
                "session_id": _session_of(str(item["SK"])),
                "role": str(item.get("role", "")),
                "content": str(item.get("content", "")),
            }
            for item in response.get("Items", [])
        ]
