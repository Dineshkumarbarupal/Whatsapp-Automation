from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from typing import Iterable

PHONE_RE = re.compile(r"^\+?[1-9]\d{7,14}$")


@dataclass(frozen=True)
class ContactRecord:
    phone: str
    display_name: str = ""
    consent_status: str = "unknown"
    source: str = "manual"


def normalize_phone(value: str) -> str:
    value = (value or "").strip()
    prefix = "+" if value.startswith("+") else ""
    digits = re.sub(r"\D", "", value)
    return prefix + digits


def validate_contact(phone: str, display_name: str = "", consent_status: str = "unknown",
                     source: str = "manual") -> ContactRecord:
    normalized = normalize_phone(phone)
    if not PHONE_RE.fullmatch(normalized):
        raise ValueError(f"Invalid international phone number: {phone!r}")
    if consent_status not in {"unknown", "granted", "revoked"}:
        raise ValueError("consent_status must be unknown, granted, or revoked")
    return ContactRecord(normalized, (display_name or "").strip()[:120], consent_status, source[:40])


def parse_contacts_csv(content: str) -> tuple[list[ContactRecord], list[str]]:
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    required = {"phone"}
    available = {name.strip().lower() for name in (reader.fieldnames or [])}
    if not required.issubset(available):
        raise ValueError("CSV must include a 'phone' column; optional columns: name, consent")
    # Normalize header keys while preserving CSV data.
    records: list[ContactRecord] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for row_number, raw in enumerate(reader, start=2):
        row = {(key or "").strip().lower(): value for key, value in raw.items()}
        try:
            consent_text = (row.get("consent") or "").strip().lower()
            consent = "granted" if consent_text in {"yes", "y", "true", "1", "approved", "granted"} else "unknown"
            record = validate_contact(row.get("phone", ""), row.get("name", ""), consent, "csv")
        except ValueError as exc:
            warnings.append(f"Row {row_number}: {exc}")
            continue
        if record.phone in seen:
            warnings.append(f"Row {row_number}: duplicate number skipped")
            continue
        seen.add(record.phone)
        records.append(record)
    return records, warnings


def export_contacts_csv(records: Iterable[dict[str, object]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["phone", "name", "consent", "source"])
    writer.writeheader()
    for record in records:
        writer.writerow({
            "phone": record.get("phone", ""),
            "name": record.get("display_name", record.get("name", "")),
            "consent": record.get("consent_status", "unknown"),
            "source": record.get("source", ""),
        })
    return output.getvalue()
