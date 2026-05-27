from __future__ import annotations

import io

import tinydata.progress as progress_module


def test_create_progress_tracker_uses_tqdm_factory(monkeypatch):
    captured = {"updates": []}

    class FakeBar:
        def update(self, step=1):
            captured["updates"].append(step)

        def close(self):
            captured["closed"] = True

    def fake_tqdm(*, total, desc, leave, dynamic_ncols):
        captured["total"] = total
        captured["desc"] = desc
        captured["leave"] = leave
        captured["dynamic_ncols"] = dynamic_ncols
        return FakeBar()

    monkeypatch.setattr(progress_module, "get_tqdm", lambda enable=True: fake_tqdm)

    tracker = progress_module._create_progress_tracker(enabled=True, total=3, description="demo")
    with tracker as bar:
        bar.update()
        bar.update(2)

    assert captured["total"] == 3
    assert captured["desc"] == "demo"
    assert captured["leave"] is False
    assert captured["dynamic_ncols"] is True
    assert captured["updates"] == [1, 2]
    assert captured["closed"] is True


def test_create_progress_tracker_defaults_to_interactive_environment(monkeypatch):
    captured = {}

    class FakeBar:
        def update(self, step=1):
            return None

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(progress_module, "is_interactive_environment", lambda: True)
    monkeypatch.setattr(progress_module, "get_tqdm", lambda enable=True: (lambda **kwargs: FakeBar()))

    tracker = progress_module._create_progress_tracker(enabled=None, total=1, description="auto")
    with tracker:
        pass

    assert isinstance(tracker, progress_module._TqdmProgressTracker)
    assert captured["closed"] is True


def test_create_progress_tracker_defaults_to_noop_in_noninteractive_environment(monkeypatch):
    monkeypatch.setattr(progress_module, "is_interactive_environment", lambda: False)

    tracker = progress_module._create_progress_tracker(enabled=None, total=2, description="auto")

    assert isinstance(tracker, progress_module._NoopProgressTracker)


def test_create_progress_tracker_explicit_false_overrides_interactive_default(monkeypatch):
    monkeypatch.setattr(progress_module, "is_interactive_environment", lambda: True)

    tracker = progress_module._create_progress_tracker(enabled=False, total=2, description="auto")

    assert isinstance(tracker, progress_module._NoopProgressTracker)


def test_create_progress_tracker_falls_back_to_text_when_tqdm_unavailable(monkeypatch):
    monkeypatch.setattr(progress_module, "get_tqdm", lambda enable=True: None)
    monkeypatch.setattr(progress_module, "is_interactive_environment", lambda: True)

    tracker = progress_module._create_progress_tracker(enabled=True, total=2, description="text")

    assert isinstance(tracker, progress_module._TextProgressTracker)


def test_text_progress_tracker_renders_to_stream():
    stream = io.StringIO()

    with progress_module._TextProgressTracker(total=2, description="text", stream=stream) as tracker:
        tracker.update()
        tracker.update()

    output = stream.getvalue()
    assert "text: 2/2" in output