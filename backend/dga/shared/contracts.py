from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleDescriptor:
    code: str
    label: str
