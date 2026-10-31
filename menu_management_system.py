"""
Menu Management System
----------------------
A console application for managing a restaurant menu: add, view, search,
update, hide/show and delete items, with a summary report. Data is stored
in a JSON file (menu.json) so the menu survives between runs.

Run program : python menu_management.py
Run tests   : python menu_management.py --test
"""

import json
import os
import sys
import tempfile
import unittest
from dataclasses import dataclass, asdict

DATA_FILE = "menu.json"
CATEGORIES = ["Starters", "Main Course", "Breads", "Desserts", "Beverages"]
MAX_NAME_LEN = 40
MAX_PRICE = 10000


class MenuError(Exception):
    """Raised when an operation on the menu is invalid."""


@dataclass
class MenuItem:
    item_id: int
    name: str
    category: str
    price: float
    is_veg: bool = True
    available: bool = True


class MenuManager:
    def __init__(self, path=DATA_FILE):
        self.path = path
        self.items = {}
        self.next_id = 1
        self.load()

    # ---------- storage ----------
    def load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            self.items = {d["item_id"]: MenuItem(**d) for d in data["items"]}
            self.next_id = data["next_id"]
        except (json.JSONDecodeError, KeyError, TypeError, OSError):
            # keep the unreadable file as a backup and start with an empty menu
            os.replace(self.path, self.path + ".bak")
            self.items, self.next_id = {}, 1

    def save(self):
        data = {"next_id": self.next_id,
                "items": [asdict(i) for i in self.items.values()]}
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.path)      # atomic replace avoids half-written files

    # ---------- validation ----------
    @staticmethod
    def _clean_name(name):
        name = " ".join(str(name).split())
        if not name:
            raise MenuError("Item name cannot be empty.")
        if len(name) > MAX_NAME_LEN:
            raise MenuError(f"Item name must be at most {MAX_NAME_LEN} characters.")
        return name

    @staticmethod
    def _clean_category(category):
        for c in CATEGORIES:
            if c.lower() == str(category).strip().lower():
                return c
        raise MenuError("Category must be one of: " + ", ".join(CATEGORIES))

    @staticmethod
    def _clean_price(price):
        try:
            price = round(float(price), 2)
        except (TypeError, ValueError):
            raise MenuError("Price must be a number.")
        if not 0 < price <= MAX_PRICE:
            raise MenuError(f"Price must be greater than 0 and at most {MAX_PRICE}.")
        return price

    def _check_duplicate(self, name, category, ignore_id=None):
        for i in self.items.values():
            if (i.item_id != ignore_id and i.category == category
                    and i.name.lower() == name.lower()):
                raise MenuError(f"'{name}' already exists in {category}.")

    # ---------- operations ----------
    def get_item(self, item_id):
        if item_id not in self.items:
            raise MenuError(f"No item with ID {item_id}.")
        return self.items[item_id]

    def add_item(self, name, category, price, is_veg=True):
        name = self._clean_name(name)
        category = self._clean_category(category)
        price = self._clean_price(price)
        self._check_duplicate(name, category)
        item = MenuItem(self.next_id, name, category, price, bool(is_veg))
        self.items[item.item_id] = item
        self.next_id += 1
        self.save()
        return item

    def update_item(self, item_id, name=None, category=None, price=None, is_veg=None):
        item = self.get_item(item_id)
        new_name = self._clean_name(name) if name is not None else item.name
        new_cat = self._clean_category(category) if category is not None else item.category
        new_price = self._clean_price(price) if price is not None else item.price
        self._check_duplicate(new_name, new_cat, ignore_id=item_id)
        item.name, item.category, item.price = new_name, new_cat, new_price
        if is_veg is not None:
            item.is_veg = bool(is_veg)
        self.save()
        return item

    def toggle_availability(self, item_id):
        item = self.get_item(item_id)
        item.available = not item.available
        self.save()
        return item

    def delete_item(self, item_id):
        item = self.get_item(item_id)
        del self.items[item_id]
        self.save()
        return item

    def search(self, keyword="", category=None, veg_only=False, available_only=False):
        keyword = keyword.strip().lower()
        result = []
        for i in self.items.values():
            if keyword and keyword not in i.name.lower():
                continue
            if category and i.category != self._clean_category(category):
                continue
            if veg_only and not i.is_veg:
                continue
            if available_only and not i.available:
                continue
            result.append(i)
        order = {c: n for n, c in enumerate(CATEGORIES)}
        return sorted(result, key=lambda i: (order[i.category], i.name.lower()))

    def summary(self):
        items = list(self.items.values())
        total = len(items)
        return {
            "total": total,
            "available": sum(i.available for i in items),
            "veg": sum(i.is_veg for i in items),
            "average_price": round(sum(i.price for i in items) / total, 2) if total else 0.0,
            "per_category": {c: sum(i.category == c for i in items) for c in CATEGORIES},
        }


# ---------------- console interface ----------------
def ask(prompt):
    return input(prompt).strip()


def ask_id(prompt="Enter item ID: "):
    try:
        return int(ask(prompt))
    except ValueError:
        raise MenuError("Item ID must be a whole number.")


def ask_yes_no(prompt):
    return ask(prompt + " (y/n): ").lower().startswith("y")


def show_table(items):
    if not items:
        print("  No items found.")
        return
    print(f"  {'ID':<4}{'Name':<26}{'Category':<13}{'Price':>8}  {'Type':<8}{'Status'}")
    print("  " + "-" * 70)
    for i in items:
        print(f"  {i.item_id:<4}{i.name:<26}{i.category:<13}{i.price:>8.2f}  "
              f"{'Veg' if i.is_veg else 'Non-Veg':<8}{'Available' if i.available else 'Hidden'}")


def choose_category():
    for n, c in enumerate(CATEGORIES, 1):
        print(f"   {n}. {c}")
    choice = ask("Category number: ")
    if choice.isdigit() and 1 <= int(choice) <= len(CATEGORIES):
        return CATEGORIES[int(choice) - 1]
    raise MenuError("Choose a number from the category list.")


def menu_add(m):
    name = ask("Item name: ")
    category = choose_category()
    price = ask("Price: ")
    item = m.add_item(name, category, price, ask_yes_no("Vegetarian?"))
    print(f"Added '{item.name}' with ID {item.item_id}.")


def menu_view(m):
    show_table(m.search())


def menu_search(m):
    keyword = ask("Name contains (blank for any): ")
    category = ask("Category (blank for any): ") or None
    veg = ask_yes_no("Vegetarian only?")
    show_table(m.search(keyword, category, veg_only=veg))


def menu_update(m):
    item = m.get_item(ask_id())
    print(f"Updating '{item.name}' (leave a field blank to keep it).")
    name = ask("New name: ") or None
    category = ask("New category: ") or None
    price = ask("New price: ") or None
    m.update_item(item.item_id, name, category, price)
    print("Item updated.")


def menu_toggle(m):
    item = m.toggle_availability(ask_id())
    print(f"'{item.name}' is now {'available' if item.available else 'hidden'}.")


def menu_delete(m):
    item = m.get_item(ask_id())
    if ask_yes_no(f"Delete '{item.name}'?"):
        m.delete_item(item.item_id)
        print("Item deleted.")
    else:
        print("Cancelled.")


def menu_summary(m):
    s = m.summary()
    print(f"  Total items   : {s['total']}")
    print(f"  Available     : {s['available']}")
    print(f"  Vegetarian    : {s['veg']}")
    print(f"  Average price : {s['average_price']:.2f}")
    for c, n in s["per_category"].items():
        print(f"    {c:<12}: {n}")


ACTIONS = {"1": menu_add, "2": menu_view, "3": menu_search, "4": menu_update,
           "5": menu_toggle, "6": menu_delete, "7": menu_summary}

MAIN_MENU = """
=========================================
        MENU MANAGEMENT SYSTEM
=========================================
 1. Add menu item
 2. View full menu
 3. Search menu
 4. Update item
 5. Show / hide item
 6. Delete item
 7. Menu summary
 0. Exit"""


def main():
    manager = MenuManager()
    while True:
        print(MAIN_MENU)
        choice = ask("Choose an option: ")
        if choice == "0":
            print("Menu saved. Goodbye!")
            return
        action = ACTIONS.get(choice)
        if not action:
            print("Invalid option.")
            continue
        try:
            action(manager)
        except MenuError as err:
            print("Error:", err)


# ---------------- unit tests (python menu_management.py --test) ----------------
class MenuTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "menu.json")
        self.m = MenuManager(self.path)

    def tearDown(self):
        self.dir.cleanup()

    def test_01_add_valid_item(self):
        a = self.m.add_item("  Paneer   Tikka ", "starters", "180", True)
        b = self.m.add_item("Dal Makhani", "Main Course", 220.5)
        self.assertEqual((a.item_id, b.item_id), (1, 2))
        self.assertEqual((a.name, a.category, a.price), ("Paneer Tikka", "Starters", 180.0))

    def test_02_empty_or_long_name_rejected(self):
        with self.assertRaises(MenuError): self.m.add_item("   ", "Starters", 100)
        with self.assertRaises(MenuError): self.m.add_item("x" * 41, "Starters", 100)

    def test_03_invalid_price_rejected(self):
        for bad in (0, -5, "abc", 10001, None):
            with self.assertRaises(MenuError): self.m.add_item("Soup", "Starters", bad)

    def test_04_invalid_category_rejected(self):
        with self.assertRaises(MenuError): self.m.add_item("Soup", "Snacks", 90)

    def test_05_duplicate_names(self):
        self.m.add_item("Lassi", "Beverages", 60)
        with self.assertRaises(MenuError): self.m.add_item("lassi", "Beverages", 70)
        self.m.add_item("Lassi", "Desserts", 70)          # other category is allowed
        self.assertEqual(len(self.m.items), 2)

    def test_06_update_item(self):
        i = self.m.add_item("Naan", "Breads", 40)
        self.m.update_item(i.item_id, price="45", name="Butter Naan")
        self.assertEqual((i.name, i.price), ("Butter Naan", 45.0))
        with self.assertRaises(MenuError): self.m.update_item(99, price=10)

    def test_07_toggle_availability(self):
        i = self.m.add_item("Naan", "Breads", 40)
        self.assertFalse(self.m.toggle_availability(i.item_id).available)
        self.assertTrue(self.m.toggle_availability(i.item_id).available)

    def test_08_delete_item(self):
        i = self.m.add_item("Naan", "Breads", 40)
        self.m.delete_item(i.item_id)
        self.assertEqual(len(self.m.items), 0)
        with self.assertRaises(MenuError): self.m.delete_item(i.item_id)

    def test_09_search_and_filters(self):
        self.m.add_item("Paneer Tikka", "Starters", 180, True)
        self.m.add_item("Chicken Tikka", "Starters", 220, False)
        self.m.add_item("Gulab Jamun", "Desserts", 80, True)
        self.assertEqual([i.name for i in self.m.search("TIKKA")], ["Chicken Tikka", "Paneer Tikka"])
        self.assertEqual(len(self.m.search(category="desserts")), 1)
        self.assertEqual(len(self.m.search(veg_only=True)), 2)
        self.m.toggle_availability(3)
        self.assertEqual(len(self.m.search(available_only=True)), 2)

    def test_10_persistence(self):
        self.m.add_item("Naan", "Breads", 40)
        self.m.add_item("Lassi", "Beverages", 60, True)
        again = MenuManager(self.path)
        self.assertEqual(len(again.items), 2)
        self.assertEqual(again.add_item("Tea", "Beverages", 30).item_id, 3)

    def test_11_corrupted_file_is_backed_up(self):
        with open(self.path, "w") as f: f.write("{not valid json")
        m = MenuManager(self.path)
        self.assertEqual(len(m.items), 0)
        self.assertTrue(os.path.exists(self.path + ".bak"))

    def test_12_summary(self):
        self.m.add_item("Paneer Tikka", "Starters", 180, True)
        self.m.add_item("Chicken Tikka", "Starters", 220, False)
        self.m.toggle_availability(2)
        s = self.m.summary()
        self.assertEqual((s["total"], s["available"], s["veg"], s["average_price"]), (2, 1, 1, 200.0))
        self.assertEqual(s["per_category"]["Starters"], 2)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        unittest.main(argv=[sys.argv[0], "-v"])
    else:
        main()