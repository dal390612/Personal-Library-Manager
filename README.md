# Features

## Item Management
- Manage two types of items: Book and DVD.
- Auto-generated unique ID for each item.
- Track checkout status and due dates.
- Book fields: title, author, pages.
- DVD fields: title, duration (minutes), rating (1–5).
- Add, edit, delete, and view item details.

## Checkout and Return System
- Check out items by entering the number of borrowing days.
- Due date is automatically calculated based on the current date.
- Prevents users from checking out items already checked out.
- Returning an item resets its availability and clears its due date.

## JSON Storage
- Items are stored in `items.json`.
- Automatically creates the file if missing.
- Detects corrupted or invalid JSON and prompts the user to reset.
- Supports backward compatibility such as `duration_minutes`.

## User Interface
- Built using Tkinter with a full dark mode UI.
- Real-time search bar with instant filtering.
- Sortable table columns.
- Double-click items to view detailed information.
- Save button writes current items to JSON with a confirmation popup.

---

# Usage Guide

## Adding Items
1. Click "Add Book" or "Add DVD".
2. Enter required details such as title, author/pages, or duration/rating.
3. Click "Add" to create the item.

## Editing Items
1. Select an item in the table.
2. Click "Edit".
3. Modify the fields.
4. Save the updated item.

## Deleting Items
1. Select an item.
2. Click "Delete" and confirm.

## Checking Out Items
1. Select an item.
2. Click "Check Out".
3. Enter the number of days to borrow.
4. The due date is generated automatically.

## Returning Items
Select a checked-out item and click "Return" to make it available again.

## Searching
Use the search bar to filter items instantly by text.

## Viewing Details
Double-click any item to view detailed information.

## Saving Data
Click "Save Changes" to store all updates in `items.json`.

---

# Error Handling

- Missing `items.json` results in a new file being created automatically.
- Invalid or corrupted JSON triggers an error prompt offering a reset.
- The system prevents invalid operations such as:
  - Checking out an already checked-out item
  - Entering invalid or incomplete item data
- Descriptive popup messages explain errors and required corrections.
- Strong validation ensures the application never crashes due to bad input.

---

# Data Validation Rules

## Book Validation
- `id`: integer  
- `title`: non-empty string  
- `author`: non-empty string  
- `pages`: positive integer  
- `is_checked_out`: boolean  
- `due_date`: null or valid `YYYY-MM-DD` date  

## DVD Validation
- `id`: integer  
- `title`: non-empty string  
- `duration`: positive integer  
- `rating`: integer between 1 and 5  
- `is_checked_out`: boolean  
- `due_date`: null or valid `YYYY-MM-DD` date  

Invalid or inconsistent entries trigger a reset prompt for the JSON file.

---

# How to Run the Application

1. Navigate to the folder where both `library_backend.py` and `items.json` are located.  
2. Open a terminal (Command Prompt / PowerShell on Windows, Terminal on macOS or Linux).  
3. Run the following command: python3 ./library_backend.py
- If you are on Windows and python3 is not recognized, try: python ./library_backend.py

---

# License

This project is provided for educational and personal use.  
Users may modify or extend the program freely.  
Redistribution for commercial purposes requires permission from the author.

