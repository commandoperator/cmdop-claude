"""Exception types for the Claude Control Plane."""

class LibraryError(Exception):
    """Base exception for all library errors."""
    pass

class ValidationError(LibraryError):
    """Raised when data validation fails."""
    pass

class FileSystemError(LibraryError):
    """Raised when file system operations fail."""
    pass

