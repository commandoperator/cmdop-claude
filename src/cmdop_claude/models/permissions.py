"""Permissions models."""
from pydantic import Field
from .base import CoreModel

class FileOperations(CoreModel):
    """File operation permissions."""
    read: bool = True
    create: bool = True
    edit: bool = True
    delete: bool = False

class SystemOperations(CoreModel):
    """System operation permissions."""
    install_packages: bool = False
    run_as_sudo: bool = False

class GitOperations(CoreModel):
    """Git operation permissions."""
    clone: bool = True
    commit: bool = True
    push: bool = False

class CodeExecution(CoreModel):
    """Code execution permissions."""
    run_scripts: bool = True
    run_tests: bool = True

class CustomRule(CoreModel):
    """Custom permission rule based on regex pattern."""
    pattern: str
    allowed: bool

class AllowedOperations(CoreModel):
    """Grouping of allowed operations."""
    file_operations: FileOperations = Field(default_factory=FileOperations)
    system_operations: SystemOperations = Field(default_factory=SystemOperations)
    git_operations: GitOperations = Field(default_factory=GitOperations)
    code_execution: CodeExecution = Field(default_factory=CodeExecution)

class PermissionsConfig(CoreModel):
    """Configuration for .permissions.json."""
    allowed_operations: AllowedOperations = Field(default_factory=AllowedOperations)
    custom_rules: list[CustomRule] = Field(default_factory=list)
