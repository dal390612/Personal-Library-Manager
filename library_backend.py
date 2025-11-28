"""Library backend for managing items, books, and DVDs.

This module defines the Item base class along with Book and DVD subclasses,
provides JSON persistence, and guards against invalid JSON by prompting the
user to optionally reset the underlying data store.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import ClassVar, Dict, List, Optional, Type

try:
    import tkinter as tk
    from tkinter import messagebox
except ModuleNotFoundError:  # pragma: no cover - tkinter unavailable in some envs
    tk = None  # type: ignore
    messagebox = None  # type: ignore


@dataclass
class Item:
    """Base representation for all library items."""

    title: str
    is_checked_out: bool = False
    due_date: Optional[str] = None
    id: Optional[int] = None

    # Class-level auto-incrementing identifier
    _id_counter: ClassVar[int] = 1

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = self._generate_id()

    @classmethod
    def _generate_id(cls) -> int:
        assigned_id = Item._id_counter
        Item._id_counter += 1
        return assigned_id

    def check_out(self, due_date: str) -> None:
        if self.is_checked_out:
            raise ValueError(f"Item '{self.title}' is already checked out.")
        self.is_checked_out = True
        self.due_date = due_date

    def return_item(self) -> None:
        if not self.is_checked_out:
            raise ValueError(f"Item '{self.title}' is not currently checked out.")
        self.is_checked_out = False
        self.due_date = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "is_checked_out": self.is_checked_out,
            "due_date": self.due_date,
            "item_type": self.__class__.__name__,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "Item":
        item_type = payload.get("item_type", "Item")
        target_cls = ITEM_TYPE_REGISTRY.get(item_type, Item)
        return target_cls._deserialize(payload)

    @classmethod
    def _deserialize(cls, payload: Dict[str, object]) -> "Item":
        return cls(
            title=str(payload.get("title", "Untitled")),
            is_checked_out=bool(payload.get("is_checked_out", False)),
            due_date=payload.get("due_date"),
            id=int(payload["id"]) if payload.get("id") is not None else None,
        )

    @classmethod
    def sync_id_counter(cls, items: List["Item"]) -> None:
        if not items:
            Item._id_counter = 1
            return
        Item._id_counter = max(item.id or 0 for item in items) + 1


@dataclass
class Book(Item):
    """Represents a book in the collection."""

    author: str = "Unknown"
    pages: int = 0

    def to_dict(self) -> Dict[str, object]:  # pragma: no cover - simple serialization
        data = super().to_dict()
        data.update({"author": self.author, "pages": self.pages})
        return data

    @classmethod
    def _deserialize(cls, payload: Dict[str, object]) -> "Book":
        return cls(
            title=str(payload.get("title", "Untitled")),
            author=str(payload.get("author", "Unknown")),
            pages=int(payload.get("pages", 0)),
            is_checked_out=bool(payload.get("is_checked_out", False)),
            due_date=payload.get("due_date"),
            id=int(payload["id"]) if payload.get("id") is not None else None,
        )


@dataclass
class DVD(Item):
    """Represents a DVD in the collection."""

    duration: int = 0  # duration in minutes
    rating: str = "NR"

    def to_dict(self) -> Dict[str, object]:  # pragma: no cover - simple serialization
        data = super().to_dict()
        data.update({"duration": self.duration, "rating": self.rating})
        return data

    @classmethod
    def _deserialize(cls, payload: Dict[str, object]) -> "DVD":
        return cls(
            title=str(payload.get("title", "Untitled")),
            duration=int(payload.get("duration", 0)),
            rating=str(payload.get("rating", "NR")),
            is_checked_out=bool(payload.get("is_checked_out", False)),
            due_date=payload.get("due_date"),
            id=int(payload["id"]) if payload.get("id") is not None else None,
        )


ITEM_TYPE_REGISTRY: Dict[str, Type[Item]] = {
    "Item": Item,
    "Book": Book,
    "DVD": DVD,
}


class LibraryRepository:
    """Handles persistence for library items."""

    def __init__(self, json_path: str = "items.json") -> None:
        self.json_path = json_path
        self.items: List[Item] = []
        self.load_items()

    def load_items(self) -> None:
        if not os.path.exists(self.json_path):
            self.items = []
            self.save_items()
            return

        try:
            with open(self.json_path, "r", encoding="utf-8") as stream:
                data = json.load(stream)
            self.items = [Item.from_dict(blob) for blob in data]
            Item.sync_id_counter(self.items)
        except json.JSONDecodeError:
            if self._prompt_reset_invalid_json():
                self.items = []
                self.save_items()
            else:
                raise

    def save_items(self) -> None:
        serialized = [item.to_dict() for item in self.items]
        with open(self.json_path, "w", encoding="utf-8") as stream:
            json.dump(serialized, stream, indent=2)

    def add_item(self, item: Item) -> None:
        self.items.append(item)
        self.save_items()

    def get_all_items(self) -> List[Item]:
        return list(self.items)

    def find_by_title(self, title: str) -> Optional[Item]:
        title_lower = title.strip().lower()
        for item in self.items:
            if item.title.lower() == title_lower:
                return item
        return None

    def _prompt_reset_invalid_json(self) -> bool:
        message = (
            "The items JSON file contains invalid JSON.\n"
            "Would you like to reset it to an empty collection?"
        )
        if tk and messagebox:
            try:
                root = tk.Tk()
                root.withdraw()
                response = messagebox.askyesno("Invalid JSON", message)
                root.destroy()
                return response
            except Exception:
                pass  # Fall back to CLI prompt if Tk cannot initialize

        while True:
            user_input = input(f"{message} (y/n): ").strip().lower()
            if user_input in {"y", "yes"}:
                return True
            if user_input in {"n", "no"}:
                return False
            print("Please respond with 'y' or 'n'.")


def demo() -> None:
    """Demonstrates repository usage without a UI."""

    repo = LibraryRepository()
    if not repo.get_all_items():
        repo.add_item(Book(title="1984", author="George Orwell", pages=328))
        repo.add_item(DVD(title="Inception", duration=148, rating="PG-13"))

    for item in repo.get_all_items():
        status = "Checked out" if item.is_checked_out else "Available"
        print(f"#{item.id} - {item.title} ({item.__class__.__name__}): {status}")


if __name__ == "__main__":
    demo()
