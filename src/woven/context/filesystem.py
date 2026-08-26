from __future__ import annotations

from pathlib import Path

from woven.context.protocol import (
    ContextError,
    ContextFile,
    ContextRequest,
    ContextSnapshot,
)


class FilesystemContext:
    """Deterministic Context backed by the local filesystem. No embeddings/vector DB."""

    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()

    def retrieve(self, request: ContextRequest) -> ContextSnapshot:
        files: dict[str, ContextFile] = {}

        for rel_path in request.paths:
            file = self._read_explicit(rel_path)
            files.setdefault(file.path, file)

        if request.name_glob is not None:
            for file in self._search_glob(request.name_glob):
                files.setdefault(file.path, file)

        if request.text_query is not None:
            for file in self._search_text(request.text_query):
                files.setdefault(file.path, file)

        return ContextSnapshot(files=list(files.values()))

    def _resolve(self, rel_path: str) -> Path:
        candidate = (self.root / rel_path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            raise ContextError(f"Path escapes root: {rel_path}") from None
        return candidate

    def _read_explicit(self, rel_path: str) -> ContextFile:
        file_path = self._resolve(rel_path)
        if not file_path.is_file():
            raise ContextError(f"File not found: {rel_path}")
        return ContextFile(path=rel_path, content=file_path.read_text())

    def _search_glob(self, pattern: str) -> list[ContextFile]:
        files = (self._to_context_file(p) for p in self._iter_files(pattern))
        return [f for f in files if f is not None]

    def _search_text(self, query: str) -> list[ContextFile]:
        matches = []
        for file_path in self._iter_files("*"):
            file = self._to_context_file(file_path)
            if file is not None and query in file.content:
                matches.append(file)
        return matches

    def _iter_files(self, pattern: str) -> list[Path]:
        return [
            p
            for p in sorted(self.root.rglob(pattern))
            if p.is_file() and not self._is_hidden(p)
        ]

    def _is_hidden(self, file_path: Path) -> bool:
        return any(
            part.startswith(".") for part in file_path.relative_to(self.root).parts
        )

    def _to_context_file(self, file_path: Path) -> ContextFile | None:
        content = self._try_read_text(file_path)
        if content is None:
            return None
        return ContextFile(path=str(file_path.relative_to(self.root)), content=content)

    @staticmethod
    def _try_read_text(file_path: Path) -> str | None:
        try:
            return file_path.read_text()
        except (UnicodeDecodeError, OSError):
            return None
