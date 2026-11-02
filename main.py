"""
WhatsApp Automation - Starter Utility

This starter script validates a contact CSV and previews personalized messages.
It does not log in to WhatsApp, send messages, or automate unsolicited outreach.

Expected CSV columns:
    phone,name,consent

Example:
    phone,name,consent
    +919876543210,Aman,yes
    +919812345678,Neha,no

Run:
    python main.py --csv contacts.csv --message "Hello {name}, this is a test."
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

LOGGER = logging.getLogger("whatsapp_automation")
PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{7,14}$")
APPROVED_CONSENT_VALUES = {"yes", "y", "true", "1", "approved"}


@dataclass(frozen=True)
class Contact:
    phone: str
    name: str
    consent: bool


def normalize_phone(value: str) -> str:
    """Remove common visual separators while preserving an optional leading +."""
    value = value.strip()
    if value.startswith("+"):
        return "+" + re.sub(r"\D", "", value[1:])
    return re.sub(r"\D", "", value)


def load_contacts(csv_path: Path) -> tuple[list[Contact], list[str]]:
    """Load contacts from CSV and return valid contacts plus row-level warnings."""
    contacts: list[Contact] = []
    warnings: list[str] = []

    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with csv_path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required = {"phone", "name", "consent"}
        available = set(reader.fieldnames or [])
        missing = required - available
        if missing:
            raise ValueError(
                "CSV is missing required column(s): " + ", ".join(sorted(missing))
            )

        seen_phones: set[str] = set()
        for row_number, row in enumerate(reader, start=2):
            phone = normalize_phone(row.get("phone", ""))
            name = (row.get("name") or "").strip() or "there"
            consent_value = (row.get("consent") or "").strip().lower()

            if not PHONE_PATTERN.fullmatch(phone):
                warnings.append(f"Row {row_number}: invalid phone number; skipped.")
                continue

            if phone in seen_phones:
                warnings.append(f"Row {row_number}: duplicate phone number; skipped.")
                continue
            seen_phones.add(phone)

            consent = consent_value in APPROVED_CONSENT_VALUES
            if not consent:
                warnings.append(
                    f"Row {row_number}: consent is not approved; contact excluded."
                )
                continue

            contacts.append(Contact(phone=phone, name=name, consent=True))

    return contacts, warnings


def build_preview(contacts: Iterable[Contact], message_template: str) -> list[str]:
    """Create previews only for contacts with recorded consent."""
    previews: list[str] = []
    for contact in contacts:
        if not contact.consent:
            continue
        message = message_template.format(name=contact.name, phone=contact.phone)
        previews.append(f"To: {contact.phone}\nMessage: {message}")
    return previews


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate opted-in contacts and preview personalized messages."
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        type=Path,
        required=True,
        help="Path to a CSV containing phone,name,consent columns.",
    )
    parser.add_argument(
        "--message",
        required=True,
        help='Message template. Supported placeholders: {name}, {phone}.',
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
        help="Logging verbosity (default: INFO).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s: %(message)s",
    )

    try:
        contacts, warnings = load_contacts(args.csv_path)
        for warning in warnings:
            LOGGER.warning(warning)

        previews = build_preview(contacts, args.message)
        print(f"\nValidated opted-in contacts: {len(contacts)}")
        print("Message previews (no messages are sent):\n")

        if not previews:
            print("No eligible contacts found.")
        else:
            for index, preview in enumerate(previews, start=1):
                print(f"--- Preview {index} ---")
                print(preview)
                print()

        LOGGER.info("Preview completed. No WhatsApp connection was opened.")
        return 0

    except (OSError, UnicodeError, csv.Error, ValueError, KeyError) as exc:
        LOGGER.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
