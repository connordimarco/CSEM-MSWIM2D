"""Tests for mswim2d._cache."""

import mswim2d._cache as cache


class _Resp:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass


def test_base_url_default():
    assert cache.BASE_URL.startswith("https://")
    assert not cache.BASE_URL.endswith("/")


def test_ensure_cached_downloads_then_reuses(monkeypatch, tmp_path):
    calls = []

    def fake_get(url, timeout=None):
        calls.append(url)
        return _Resp(b"payload")

    monkeypatch.setattr(cache, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(cache.requests, "get", fake_get)

    path = cache.ensure_cached("dir/sub/file.csv")
    assert path == tmp_path / "dir" / "sub" / "file.csv"
    assert path.read_bytes() == b"payload"
    assert calls == [f"{cache.BASE_URL}/dir/sub/file.csv"]

    # Second call is served from cache (no new download).
    again = cache.ensure_cached("dir/sub/file.csv")
    assert again == path
    assert len(calls) == 1


def test_ensure_cached_refresh_redownloads(monkeypatch, tmp_path):
    calls = []

    def fake_get(url, timeout=None):
        calls.append(url)
        return _Resp(b"v2")

    monkeypatch.setattr(cache, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(cache.requests, "get", fake_get)

    (tmp_path / "m.json").write_bytes(b"v1")
    path = cache.ensure_cached("m.json", refresh=True)
    assert path.read_bytes() == b"v2"
    assert len(calls) == 1


def test_fetch_json(monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(cache.requests, "get", lambda url, timeout=None: _Resp(b'{"a": 1}'))
    assert cache.fetch_json("x.json") == {"a": 1}
