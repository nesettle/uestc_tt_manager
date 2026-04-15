from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class QualificationRecord:
    source: str
    sheet: str
    row_number: int
    name: str
    college: str
    qq: str
    normalized_name: str
    normalized_college: str
    normalized_qq: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FormRecord:
    source: str
    row_number: int
    created_at: str
    updated_at: str
    serial_number: str
    name: str
    college: str
    qq: str
    normalized_name: str
    normalized_college: str
    normalized_qq: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DuplicateRow:
    source: str
    key_type: str
    match_key: str
    name: str
    college: str
    qq: str
    details: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Recipient:
    qq: str
    name: str
    college: str
    message: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
