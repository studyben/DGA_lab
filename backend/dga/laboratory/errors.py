class LaboratoryError(Exception):
    """Stable application error for laboratory operations."""

    def __init__(self, code: str, status: int = 422, *, details: dict | None = None):
        self.code = code
        self.status = status
        self.details = details
        super().__init__(code)
