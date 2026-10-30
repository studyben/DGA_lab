"""Versioned, strict laboratory-owned staging inputs; no formal result commands."""
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

XLSX_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
CSV_TYPE = 'text/csv'
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_REQUEST_BYTES = 32 * 1024 * 1024


class ImportInput(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class SourceChoice(ImportInput):
    key: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_-]{0,79}$')
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator('reason')
    @classmethod
    def reason_text(cls, value):
        if not value.strip() or '\x00' in value:
            raise ValueError('invalid_source_decision')
        return value.strip()


class NewSource(SourceChoice):
    decision: Literal['NEW']
    proposed_name: str = Field(min_length=1, max_length=200)
    source_kind: Literal['IN_HOUSE', 'THIRD_PARTY']
    confirm_distinct: bool = Field(strict=True)
    candidate_digest: str = Field(pattern=r'^[0-9a-f]{64}$')

    @field_validator('proposed_name')
    @classmethod
    def name_text(cls, value):
        value = value.strip()
        if not value or any(ord(ch) < 32 for ch in value):
            raise ValueError('invalid_source_decision')
        return value

    @model_validator(mode='after')
    def confirmed(self):
        if not self.confirm_distinct:
            raise ValueError('source_confirmation_required')
        return self


class ReferenceSource(SourceChoice):
    decision: Literal['REFERENCE']
    source_lab_id: UUID


SourceDecision = Annotated[NewSource | ReferenceSource, Field(discriminator='decision')]


class CreateImport(ImportInput):
    format_version: int = Field(default=1, strict=True)
    input_format: Literal['XLSX', 'CSV_PAIR']
    purpose: Literal['HISTORICAL', 'DAILY']
    source_timezone: str | None = Field(default=None, min_length=1, max_length=100)
    source_timezone_confirmed: bool = Field(default=False, strict=True)
    source_labs: tuple[SourceDecision, ...] = Field(default=(), max_length=500)

    @model_validator(mode='after')
    def coherent(self):
        if self.format_version != 1 or (self.source_timezone_confirmed and not self.source_timezone):
            raise ValueError('invalid_import_input')
        if len({item.key for item in self.source_labs}) != len(self.source_labs):
            raise ValueError('invalid_source_decision')
        if self.source_timezone:
            try:
                ZoneInfo(self.source_timezone)
            except (ZoneInfoNotFoundError, ValueError):
                raise ValueError('invalid_timezone') from None
        return self



class ImportMetadata(ImportInput):
    purpose: Literal['HISTORICAL', 'DAILY'] | None = None
    source_timezone: str | None = Field(default=None, min_length=1, max_length=100)
    source_timezone_confirmed: bool | None = Field(default=None, strict=True)


class RowChange(ImportInput):
    row_id: UUID
    values: dict[str, str | bool | int | None] = Field(min_length=1,max_length=39)

    @field_validator('values',mode='before')
    @classmethod
    def scalar_values(cls, values):
        if not isinstance(values,dict): raise ValueError('invalid_import_input')
        for field,value in values.items():
            if not isinstance(field,str) or type(value) not in (str,bool,int,type(None)):
                raise ValueError('invalid_import_input')
            if field.endswith('_value') and value is not None and not isinstance(value,str):
                raise ValueError('invalid_import_input')
            if isinstance(value,str):
                if len(value)>32767 or '\x00' in value:
                    raise ValueError('invalid_import_input')
                if field in ('notes','source_note','source_qa') and len(value)>2000:
                    raise ValueError('invalid_import_input')
        return values


class ReviseImport(ImportInput):
    expected_revision: int = Field(strict=True, ge=0)
    reason: str = Field(min_length=1, max_length=1000)
    metadata: ImportMetadata | None = None
    source_labs: tuple[SourceDecision, ...] = Field(default=(), max_length=500)
    active_files: dict[Literal['WORKBOOK', 'SAMPLES', 'TESTS'], UUID] | None = Field(default=None, max_length=3)
    changes: tuple[RowChange, ...] = Field(default=(), max_length=2500)

    @model_validator(mode='after')
    def coherent(self):
        if not self.reason.strip() or '\x00' in self.reason:
            raise ValueError('invalid_import_input')
        if not self.metadata and not self.source_labs and not self.active_files and not self.changes:
            raise ValueError('invalid_import_input')
        if (self.active_files and self.changes) or len({x.row_id for x in self.changes})!=len(self.changes):
            raise ValueError('invalid_import_input')
        if len({x.key for x in self.source_labs}) != len(self.source_labs):
            raise ValueError('invalid_source_decision')
        return self


class ValidationInput(ImportInput):
    expected_revision: int = Field(strict=True, ge=0)

