class LaboratoryError(Exception):
    """Stable application error for laboratory operations."""

    def __init__(self, code: str, status: int = 422):
        self.code = code
        self.status = status
        super().__init__(code)
