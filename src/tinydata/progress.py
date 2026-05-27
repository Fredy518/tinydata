"""Environment-aware progress helpers."""

from __future__ import annotations

import sys
from typing import Any, Callable, Optional


class _NoopProgressTracker:
    def __enter__(self) -> _NoopProgressTracker:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    def update(self, step: int = 1) -> None:
        return None

    def close(self) -> None:
        return None


class _TextProgressTracker(_NoopProgressTracker):
    def __init__(self, *, total: int, description: str, stream: Any = None) -> None:
        self.total = max(0, int(total))
        self.description = description
        self.stream = stream or sys.stderr
        self.completed = 0
        self._closed = False
        self._last_line_length = 0

    def __enter__(self) -> _TextProgressTracker:
        if self.total > 0:
            self._render()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        self.close()
        return False

    def update(self, step: int = 1) -> None:
        if self._closed or self.total <= 0:
            return
        self.completed = min(self.total, self.completed + max(0, int(step)))
        self._render()

    def close(self) -> None:
        if self._closed:
            return
        if self.total > 0:
            self._render()
            self.stream.write("\n")
            self.stream.flush()
        self._closed = True

    def _render(self) -> None:
        total = self.total or 1
        ratio = self.completed / total
        width = 24
        filled = min(width, int(round(ratio * width)))
        bar = "#" * filled + "-" * (width - filled)
        line = f"{self.description}: {self.completed}/{self.total} [{bar}] {ratio:6.1%}"
        padding = " " * max(0, self._last_line_length - len(line))
        self.stream.write(f"\r{line}{padding}")
        self.stream.flush()
        self._last_line_length = len(line)


class _TqdmProgressTracker(_NoopProgressTracker):
    def __init__(self, *, total: int, description: str, tqdm_factory: Callable[..., Any]) -> None:
        self.total = max(0, int(total))
        self.description = description
        self.tqdm_factory = tqdm_factory
        self._progress_bar: Any = None

    def __enter__(self) -> _TqdmProgressTracker:
        if self.total > 0:
            self._progress_bar = self.tqdm_factory(
                total=self.total,
                desc=self.description,
                leave=False,
                dynamic_ncols=True,
            )
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        self.close()
        return False

    def update(self, step: int = 1) -> None:
        if self._progress_bar is None:
            return
        self._progress_bar.update(max(0, int(step)))

    def close(self) -> None:
        if self._progress_bar is None:
            return
        self._progress_bar.close()
        self._progress_bar = None


def is_interactive_environment() -> bool:
    if hasattr(sys, "ps1") or bool(getattr(sys.flags, "interactive", 0)):
        return True
    try:
        shell = get_ipython().__class__.__name__  # type: ignore[name-defined]
        return shell in {"ZMQInteractiveShell", "TerminalInteractiveShell"}
    except (NameError, ImportError):
        return False


def resolve_progress_enabled(enabled: Optional[bool]) -> bool:
    if enabled is None:
        return is_interactive_environment()
    return bool(enabled)


def get_tqdm(enable: bool = True) -> Optional[Callable[..., Any]]:
    if not enable:
        return None
    try:
        shell = get_ipython().__class__.__name__  # type: ignore[name-defined]
        if shell == "ZMQInteractiveShell":
            try:
                from tqdm.notebook import tqdm

                return tqdm
            except ImportError:
                pass
        from tqdm.auto import tqdm

        return tqdm
    except (NameError, ImportError):
        try:
            from tqdm.auto import tqdm

            return tqdm
        except ImportError:
            return None


def _create_progress_tracker(*, enabled: Optional[bool], total: int, description: str) -> _NoopProgressTracker:
    if not resolve_progress_enabled(enabled) or total <= 0:
        return _NoopProgressTracker()
    tqdm_factory = get_tqdm(enable=True)
    if tqdm_factory is not None:
        return _TqdmProgressTracker(total=total, description=description, tqdm_factory=tqdm_factory)
    return _TextProgressTracker(total=total, description=description)