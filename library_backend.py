"""Library backend and Tkinter GUI for managing books and DVDs."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Dict, List, Optional, Type

try:
    import tkinter as tk
    from tkinter import messagebox, simpledialog, ttk
except ModuleNotFoundError:  # pragma: no cover - tkinter unavailable in some envs
    tk = None  # type: ignore
    messagebox = None  # type: ignore
    simpledialog = None  # type: ignore
    ttk = None  # type: ignore

DATE_FORMAT = "%Y-%m-%d"
VALID_ITEM_TYPES = {"Book", "DVD"}


def ensure_due_date_string(value: str) -> str:
    """Validate and normalize a due date string (YYYY-MM-DD)."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Due date must be a non-empty YYYY-MM-DD string.")
    trimmed = value.strip()
    try:
        datetime.strptime(trimmed, DATE_FORMAT)
    except ValueError as exc:  # pragma: no cover - straightforward validation
        raise ValueError(
            f"Due date must follow {DATE_FORMAT} format."
        ) from exc
    return trimmed


def _require_string(value: Any, field: str, index: int, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Row {index + 1}: {field} must be a string.")
    trimmed = value.strip()
    if not trimmed and not allow_empty:
        raise ValueError(f"Row {index + 1}: {field} cannot be empty.")
    return trimmed if not allow_empty else value


def _require_bool(value: Any, index: int) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"Row {index + 1}: is_checked_out must be true or false.")


def _require_positive_int(
    value: Any, field: str, index: int, *, allow_zero: bool = False
) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Row {index + 1}: {field} must be a positive integer."
        ) from exc
    if allow_zero:
        if number < 0:
            raise ValueError(f"Row {index + 1}: {field} cannot be negative.")
    else:
        if number <= 0:
            raise ValueError(f"Row {index + 1}: {field} must be greater than zero.")
    return number


def _require_rating(value: Any, index: int) -> int:
    rating = _require_positive_int(value, "rating", index)
    if not 1 <= rating <= 5:
        raise ValueError(f"Row {index + 1}: rating must be between 1 and 5.")
    return rating


def _require_date_or_none(value: Any, index: int) -> Optional[str]:
    if value in {None, ""}:
        return None
    if not isinstance(value, str):
        raise ValueError(
            f"Row {index + 1}: due_date must be null or a {DATE_FORMAT} string."
        )
    ensure_due_date_string(value)
    return value.strip()


def _normalize_item_type(
    primary: Any, fallback: Any, index: int
) -> str:
    candidate = primary or fallback
    if not isinstance(candidate, str):
        raise ValueError(
            f"Row {index + 1}: type must be one of {', '.join(sorted(VALID_ITEM_TYPES))}."
        )
    candidate = candidate.strip()
    if candidate not in VALID_ITEM_TYPES:
        raise ValueError(
            f"Row {index + 1}: type must be one of {', '.join(sorted(VALID_ITEM_TYPES))}."
        )
    return candidate


def _normalize_json_row(row: Dict[str, Any], index: int) -> Dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError(f"Row {index + 1}: each entry must be a JSON object.")

    normalized: Dict[str, Any] = dict(row)
    normalized["id"] = _require_positive_int(row.get("id"), "id", index)
    normalized["title"] = _require_string(row.get("title"), "title", index)
    normalized["is_checked_out"] = _require_bool(row.get("is_checked_out"), index)
    normalized["due_date"] = _require_date_or_none(row.get("due_date"), index)

    item_type = _normalize_item_type(row.get("type"), row.get("item_type"), index)
    normalized["type"] = item_type
    normalized["item_type"] = item_type

    if item_type == "Book":
        normalized["author"] = _require_string(row.get("author"), "author", index)
        normalized["pages"] = _require_positive_int(row.get("pages"), "pages", index)
    else:
        duration_source = row.get("duration", row.get("duration_minutes"))
        normalized["duration"] = _require_positive_int(
            duration_source, "duration", index
        )
        normalized["duration_minutes"] = normalized["duration"]
        normalized["rating"] = _require_rating(row.get("rating"), index)

    return normalized


@dataclass
class Item:
    """Base representation for all library items."""

    title: str
    is_checked_out: bool = False
    due_date: Optional[str] = None
    id: Optional[int] = None

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
        self.due_date = ensure_due_date_string(due_date)

    def return_item(self) -> None:
        if not self.is_checked_out:
            raise ValueError(f"Item '{self.title}' is not currently checked out.")
        self.is_checked_out = False
        self.due_date = None

    def to_dict(self) -> Dict[str, object]:  # pragma: no cover - simple serialization
        item_type = self.__class__.__name__
        return {
            "id": self.id,
            "title": self.title,
            "is_checked_out": self.is_checked_out,
            "due_date": self.due_date,
            "item_type": item_type,
            "type": item_type,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "Item":
        item_type = payload.get("item_type", payload.get("type", "Item"))
        target_cls = ITEM_TYPE_REGISTRY.get(str(item_type), Item)
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
    pages: int = 1

    def to_dict(self) -> Dict[str, object]:  # pragma: no cover - simple serialization
        data = super().to_dict()
        data.update({"author": self.author, "pages": self.pages})
        return data

    @classmethod
    def _deserialize(cls, payload: Dict[str, object]) -> "Book":
        return cls(
            title=str(payload.get("title", "Untitled")),
            author=str(payload.get("author", "Unknown")),
            pages=int(payload.get("pages", 1)),
            is_checked_out=bool(payload.get("is_checked_out", False)),
            due_date=payload.get("due_date"),
            id=int(payload["id"]) if payload.get("id") is not None else None,
        )


@dataclass
class DVD(Item):
    """Represents a DVD in the collection."""

    duration: int = 1
    rating: int = 3

    def to_dict(self) -> Dict[str, object]:  # pragma: no cover - simple serialization
        data = super().to_dict()
        data.update(
            {"duration": self.duration, "duration_minutes": self.duration, "rating": self.rating}
        )
        return data

    @classmethod
    def _deserialize(cls, payload: Dict[str, object]) -> "DVD":
        duration_value = payload.get("duration", payload.get("duration_minutes", 1))
        return cls(
            title=str(payload.get("title", "Untitled")),
            duration=int(duration_value),
            rating=int(payload.get("rating", 3)),
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
    """Handles persistence and validation for library items."""

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
            normalized_rows = self._normalize_rows(data)
            self.items = [Item.from_dict(blob) for blob in normalized_rows]
            Item.sync_id_counter(self.items)
        except json.JSONDecodeError:
            if self._prompt_reset_invalid_json("The JSON file is malformed."):
                self.items = []
                self.save_items()
            else:
                raise
        except ValueError as exc:
            if self._prompt_reset_invalid_json(str(exc)):
                self.items = []
                self.save_items()
            else:
                raise

    def _normalize_rows(self, payload: Any) -> List[Dict[str, Any]]:
        if payload in (None, ""):
            return []
        if not isinstance(payload, list):
            raise ValueError("Items JSON must contain a list of records.")
        return [_normalize_json_row(row, idx) for idx, row in enumerate(payload)]

    def save_items(self) -> None:
        serialized = [item.to_dict() for item in self.items]
        with open(self.json_path, "w", encoding="utf-8") as stream:
            json.dump(serialized, stream, indent=2)

    def add_item(self, item: Item) -> None:
        self.items.append(item)
        self.save_items()

    def delete_item(self, item_id: int) -> None:
        self.items = [item for item in self.items if item.id != item_id]
        self.save_items()

    def get_all_items(self) -> List[Item]:
        return list(self.items)

    def get_item_by_id(self, item_id: int) -> Optional[Item]:
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def _prompt_reset_invalid_json(self, detail: str) -> bool:
        message = (
            "The items JSON file contains invalid data.\n"
            f"Details: {detail}\n\n"
            "Would you like to reset it to an empty collection?"
        )
        if tk and messagebox:
            try:
                root = tk.Tk()
                root.withdraw()
                response = messagebox.askyesno("Invalid JSON", message)
                root.destroy()
                return bool(response)
            except Exception:
                pass  # Fall back to CLI prompt if Tk cannot initialize

        while True:
            user_input = input(f"{message} (y/n): ").strip().lower()
            if user_input in {"y", "yes"}:
                return True
            if user_input in {"n", "no"}:
                return False
            print("Please respond with 'y' or 'n'.")


class LibraryApp:
    """Tkinter GUI for managing the library inventory."""

    def __init__(self, json_path: str = "items.json") -> None:
        if tk is None or ttk is None or messagebox is None:
            raise RuntimeError("Tkinter is not available on this system.")

        self.repo = LibraryRepository(json_path)
        self.root = tk.Tk()
        self.root.title("Library Manager")

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_table())
        self.sort_column = "id"
        self.sort_reverse = False

        self.tree: ttk.Treeview
        self._build_ui()
        self.refresh_table()

    def run(self) -> None:
        self.root.mainloop()

    def _build_ui(self) -> None:
        search_frame = ttk.Frame(self.root, padding=(10, 10, 10, 0))
        search_frame.pack(fill="x")

        ttk.Label(search_frame, text="Search:").pack(side="left")
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))

        tree_frame = ttk.Frame(self.root, padding=10)
        tree_frame.pack(fill="both", expand=True)

        columns = ("id", "title", "type", "status", "due_date")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        headings = {
            "id": "ID",
            "title": "Title",
            "type": "Type",
            "status": "Status",
            "due_date": "Due Date",
        }
        for column in columns:
            self.tree.heading(
                column,
                text=headings[column],
                command=lambda col=column: self.sort_by_column(col),
            )
            self.tree.column(column, anchor="center")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self.show_item_details)

        button_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        button_frame.pack(fill="x")

        buttons = [
            ("Add Book", self.add_book),
            ("Add DVD", self.add_dvd),
            ("Edit", self.edit_item),
            ("Delete", self.delete_item),
            ("Check Out", self.check_out_item),
            ("Return", self.return_item),
            ("Save", self.save_changes),
        ]
        for text, command in buttons:
            ttk.Button(button_frame, text=text, command=command).pack(
                side="left", padx=5, pady=5
            )

    def refresh_table(self) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)

        items = self._get_filtered_items()
        for item in items:
            status = "Checked Out" if item.is_checked_out else "Available"
            due_date = item.due_date or ""
            self.tree.insert(
                "",
                "end",
                iid=str(item.id),
                values=(item.id, item.title, item.__class__.__name__, status, due_date),
            )

    def _get_filtered_items(self) -> List[Item]:
        query = self.search_var.get().strip().lower()
        items = self.repo.get_all_items()
        if query:
            filtered: List[Item] = []
            for item in items:
                haystack = " ".join(
                    filter(
                        None,
                        [
                            str(item.id),
                            item.title,
                            item.__class__.__name__,
                            getattr(item, "author", ""),
                        ],
                    )
                ).lower()
                if query in haystack:
                    filtered.append(item)
            items = filtered
        return self._sort_items(items)

    def _sort_items(self, items: List[Item]) -> List[Item]:
        key_map = {
            "id": lambda i: i.id or 0,
            "title": lambda i: i.title.lower(),
            "type": lambda i: i.__class__.__name__,
            "status": lambda i: i.is_checked_out,
            "due_date": lambda i: (i.due_date is None, i.due_date or ""),
        }
        key_fn = key_map.get(self.sort_column, key_map["id"])
        return sorted(items, key=key_fn, reverse=self.sort_reverse)

    def sort_by_column(self, column: str) -> None:
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        self.refresh_table()

    def add_book(self) -> None:
        self._open_item_form("Book")

    def add_dvd(self) -> None:
        self._open_item_form("DVD")

    def edit_item(self) -> None:
        item = self._require_selection("Select an item to edit.")
        if item:
            self._open_item_form(item.__class__.__name__, item)

    def delete_item(self) -> None:
        item = self._require_selection("Select an item to delete.")
        if not item:
            return
        if not messagebox.askyesno(
            "Delete Item", f"Are you sure you want to delete '{item.title}'?", parent=self.root
        ):
            return
        self.repo.delete_item(item.id or 0)
        self.refresh_table()

    def check_out_item(self) -> None:
        item = self._require_selection("Select an item to check out.")
        if not item:
            return
        if item.is_checked_out:
            messagebox.showerror("Error", f"'{item.title}' is already checked out.", parent=self.root)
            return
        prompt = "Enter due date (YYYY-MM-DD):"
        due_date = simpledialog.askstring("Check Out", prompt, parent=self.root)
        if due_date is None:
            return
        try:
            item.check_out(ensure_due_date_string(due_date))
        except ValueError as exc:
            messagebox.showerror("Invalid Due Date", str(exc), parent=self.root)
            return
        self.repo.save_items()
        self.refresh_table()

    def return_item(self) -> None:
        item = self._require_selection("Select an item to return.")
        if not item:
            return
        if not item.is_checked_out:
            messagebox.showerror("Error", f"'{item.title}' is not checked out.", parent=self.root)
            return
        item.return_item()
        self.repo.save_items()
        self.refresh_table()

    def save_changes(self) -> None:
        self.repo.save_items()
        messagebox.showinfo("Saved", "Items have been saved to disk.", parent=self.root)

    def show_item_details(self, _event: Optional[tk.Event] = None) -> None:
        item = self._get_selected_item()
        if not item:
            return
        details = [f"Title: {item.title}", f"Type: {item.__class__.__name__}"]
        if isinstance(item, Book):
            details.append(f"Author: {item.author}")
            details.append(f"Pages: {item.pages}")
        elif isinstance(item, DVD):
            details.append(f"Duration: {item.duration} minutes")
            details.append(f"Rating: {item.rating}")
        status = "Checked Out" if item.is_checked_out else "Available"
        details.append(f"Status: {status}")
        details.append(f"Due Date: {item.due_date or 'N/A'}")
        messagebox.showinfo("Item Details", "\n".join(details), parent=self.root)

    def _open_item_form(self, item_type: str, item: Optional[Item] = None) -> None:
        window = tk.Toplevel(self.root)
        is_edit = item is not None
        window.title(f"{'Edit' if is_edit else 'Add'} {item_type}")
        window.transient(self.root)
        window.grab_set()

        fields = [("Title", "title")]
        if item_type == "Book":
            fields.extend([("Author", "author"), ("Pages", "pages")])
        elif item_type == "DVD":
            fields.extend(
                [("Duration (minutes)", "duration"), ("Rating (1-5)", "rating")]
            )
        else:
            messagebox.showerror("Unsupported", f"Unknown item type: {item_type}.", parent=window)
            window.destroy()
            return

        entries: Dict[str, ttk.Entry] = {}
        for row_index, (label_text, key) in enumerate(fields):
            ttk.Label(window, text=label_text).grid(row=row_index, column=0, padx=5, pady=5, sticky="w")
            entry = ttk.Entry(window, width=40)
            entry.grid(row=row_index, column=1, padx=5, pady=5, sticky="ew")
            default_value = ""
            if is_edit and item is not None:
                if key == "title":
                    default_value = item.title
                elif key == "author" and isinstance(item, Book):
                    default_value = item.author
                elif key == "pages" and isinstance(item, Book):
                    default_value = str(item.pages)
                elif key == "duration" and isinstance(item, DVD):
                    default_value = str(item.duration)
                elif key == "rating" and isinstance(item, DVD):
                    default_value = str(item.rating)
            entry.insert(0, default_value)
            entries[key] = entry
        window.columnconfigure(1, weight=1)

        def submit() -> None:
            values = {key: entry.get() for key, entry in entries.items()}
            try:
                if item_type == "Book":
                    payload = self._validate_book_payload(values)
                    if item is None:
                        self.repo.add_item(Book(**payload))
                    else:
                        assert isinstance(item, Book)
                        item.title = payload["title"]
                        item.author = payload["author"]
                        item.pages = payload["pages"]
                        self.repo.save_items()
                else:
                    payload = self._validate_dvd_payload(values)
                    if item is None:
                        self.repo.add_item(DVD(**payload))
                    else:
                        assert isinstance(item, DVD)
                        item.title = payload["title"]
                        item.duration = payload["duration"]
                        item.rating = payload["rating"]
                        self.repo.save_items()
            except ValueError as exc:
                messagebox.showerror("Invalid Data", str(exc), parent=window)
                return

            window.destroy()
            self.refresh_table()

        button_row = len(fields)
        ttk.Button(window, text="Save", command=submit).grid(
            row=button_row, column=0, padx=5, pady=(10, 5), sticky="ew"
        )
        ttk.Button(window, text="Cancel", command=window.destroy).grid(
            row=button_row, column=1, padx=5, pady=(10, 5), sticky="ew"
        )

    def _validate_book_payload(self, values: Dict[str, str]) -> Dict[str, Any]:
        title = values.get("title", "").strip()
        author = values.get("author", "").strip()
        pages_raw = values.get("pages", "")
        if not title:
            raise ValueError("Title is required.")
        if not author:
            raise ValueError("Author is required.")
        pages = self._coerce_positive_int_from_entry(pages_raw, "Pages")
        return {"title": title, "author": author, "pages": pages}

    def _validate_dvd_payload(self, values: Dict[str, str]) -> Dict[str, Any]:
        title = values.get("title", "").strip()
        duration_raw = values.get("duration", "")
        rating_raw = values.get("rating", "")
        if not title:
            raise ValueError("Title is required.")
        duration = self._coerce_positive_int_from_entry(duration_raw, "Duration")
        rating = self._coerce_positive_int_from_entry(rating_raw, "Rating")
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5.")
        return {"title": title, "duration": duration, "rating": rating}

    def _coerce_positive_int_from_entry(self, value: str, field_label: str) -> int:
        try:
            number = int(value)
        except ValueError as exc:
            raise ValueError(f"{field_label} must be a positive integer.") from exc
        if number <= 0:
            raise ValueError(f"{field_label} must be greater than zero.")
        return number

    def _get_selected_item(self) -> Optional[Item]:
        selection = self.tree.selection()
        if not selection:
            return None
        try:
            item_id = int(selection[0])
        except ValueError:
            return None
        return self.repo.get_item_by_id(item_id)

    def _require_selection(self, message: str) -> Optional[Item]:
        item = self._get_selected_item()
        if not item:
            messagebox.showerror("Selection Required", message, parent=self.root)
        return item


def main() -> None:
    if tk is None or ttk is None or messagebox is None:
        print("Tkinter is not available in this environment. GUI cannot be displayed.")
        return

    app = LibraryApp()
    app.run()


if __name__ == "__main__":
    main()
