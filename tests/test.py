"""Basic FileManager contract; this used to be a machine-specific demo script."""

from app.workspace.file_manager import FileManager


def test_file_manager_lists_the_active_workspace_without_assuming_demo_files():
    assert isinstance(FileManager.list_files(), list)
