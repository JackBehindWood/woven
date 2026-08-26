import pytest

from woven.context import ContextError, ContextRequest, FilesystemContext


def test_explicit_file_selection_reads_content(tmp_path):
    (tmp_path / "a.txt").write_text("hello a")
    context = FilesystemContext(tmp_path)

    snapshot = context.retrieve(ContextRequest(purpose="p", paths=["a.txt"]))

    assert len(snapshot.files) == 1
    assert snapshot.files[0].path == "a.txt"
    assert snapshot.files[0].content == "hello a"


def test_explicit_missing_file_raises_context_error(tmp_path):
    context = FilesystemContext(tmp_path)

    with pytest.raises(ContextError):
        context.retrieve(ContextRequest(purpose="p", paths=["missing.txt"]))


def test_explicit_path_escaping_root_raises_context_error(tmp_path):
    context = FilesystemContext(tmp_path)

    with pytest.raises(ContextError):
        context.retrieve(ContextRequest(purpose="p", paths=["../escape.txt"]))


def test_name_glob_search_finds_matching_files(tmp_path):
    (tmp_path / "a.py").write_text("python a")
    (tmp_path / "b.txt").write_text("text b")
    context = FilesystemContext(tmp_path)

    snapshot = context.retrieve(ContextRequest(purpose="p", name_glob="*.py"))

    assert [f.path for f in snapshot.files] == ["a.py"]


def test_name_glob_search_recurses_into_subdirectories(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.py").write_text("nested")
    context = FilesystemContext(tmp_path)

    snapshot = context.retrieve(ContextRequest(purpose="p", name_glob="*.py"))

    assert [f.path for f in snapshot.files] == ["sub/nested.py"]


def test_text_search_finds_files_containing_query(tmp_path):
    (tmp_path / "a.txt").write_text("contains needle here")
    (tmp_path / "b.txt").write_text("no match")
    context = FilesystemContext(tmp_path)

    snapshot = context.retrieve(ContextRequest(purpose="p", text_query="needle"))

    assert [f.path for f in snapshot.files] == ["a.txt"]


def test_text_search_skips_hidden_directories(tmp_path):
    hidden = tmp_path / ".git"
    hidden.mkdir()
    (hidden / "config").write_text("needle")
    context = FilesystemContext(tmp_path)

    snapshot = context.retrieve(ContextRequest(purpose="p", text_query="needle"))

    assert snapshot.files == []


def test_retrieve_combines_and_dedupes_across_modes(tmp_path):
    (tmp_path / "a.py").write_text("needle inside")
    context = FilesystemContext(tmp_path)

    snapshot = context.retrieve(
        ContextRequest(
            purpose="p",
            paths=["a.py"],
            name_glob="*.py",
            text_query="needle",
        )
    )

    assert [f.path for f in snapshot.files] == ["a.py"]


def test_retrieve_with_no_criteria_returns_empty_snapshot(tmp_path):
    context = FilesystemContext(tmp_path)

    snapshot = context.retrieve(ContextRequest(purpose="p"))

    assert snapshot.files == []
