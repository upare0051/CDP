import pytest

from app.services import dittofeed_client


WORKSPACE_ID = "f9a3186c-4ff7-4a1f-bc8d-1d8a790651c3"


def test_extract_workspace_id_from_dashboard_payload():
    payload = '{"workspaceId":"f9a3186c-4ff7-4a1f-bc8d-1d8a790651c3","workspaceName":"Alo"}'

    assert dittofeed_client._extract_workspace_id(payload) == "f9a3186c-4ff7-4a1f-bc8d-1d8a790651c3"


def test_workspace_id_falls_back_to_dashboard_payload(monkeypatch):
    workspace_id = "f9a3186c-4ff7-4a1f-bc8d-1d8a790651c3"
    calls = []

    class FakeResponse:
        def __init__(self, is_success, text=""):
            self.is_success = is_success
            self.text = text

        def json(self):
            return {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            calls.append(url)
            if url.endswith("/api/workspaces"):
                return FakeResponse(False)
            return FakeResponse(True, f'{{"workspaceId":"{workspace_id}"}}')

    monkeypatch.setattr(dittofeed_client, "_cached_workspace_id", None)
    monkeypatch.setattr(dittofeed_client, "_base_url", lambda: "http://journeys-lite:3000")
    monkeypatch.setattr(dittofeed_client.settings, "dittofeed_workspace_id", None)
    monkeypatch.setattr(dittofeed_client.httpx, "Client", FakeClient)

    assert dittofeed_client._workspace_id() == workspace_id
    assert calls == [
        "http://journeys-lite:3000/api/workspaces",
        "http://journeys-lite:3000/dashboard/journeys",
    ]


class _FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self.is_success = 200 <= status_code < 300
        self._payload = payload or {}
        self.text = text or ""

    def json(self):
        return self._payload


class _FakeClient:
    """Records the last request and returns a fixed FakeResponse."""

    last: dict = {}

    def __init__(self, response: _FakeResponse):
        self._response = response

    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def put(self, url, json=None):
        _FakeClient.last = {"method": "PUT", "url": url, "json": json}
        return self._response

    def post(self, url, json=None):
        _FakeClient.last = {"method": "POST", "url": url, "json": json}
        return self._response

    def request(self, method, url, params=None, json=None):
        _FakeClient.last = {
            "method": method,
            "url": url,
            "params": params,
            "json": json,
        }
        return self._response


@pytest.fixture
def stub_workspace(monkeypatch):
    monkeypatch.setattr(dittofeed_client, "_workspace_id", lambda: WORKSPACE_ID)
    monkeypatch.setattr(
        dittofeed_client, "_base_url", lambda: "http://journeys-lite:3000"
    )


def _install_fake_client(monkeypatch, response: _FakeResponse):
    fake = _FakeClient(response)
    monkeypatch.setattr(dittofeed_client.httpx, "Client", fake)
    return fake


def test_upsert_manual_segment_creates_new(stub_workspace, monkeypatch):
    new_id = "fea51159-3e5a-42a5-a969-9e3356f2937f"
    _install_fake_client(
        monkeypatch,
        _FakeResponse(200, {"id": new_id, "name": "seg-7"}),
    )

    df_id = dittofeed_client.upsert_manual_segment("seg-7")

    assert df_id == new_id
    body = _FakeClient.last["json"]
    assert _FakeClient.last["method"] == "PUT"
    assert _FakeClient.last["url"].endswith("/api/segments/")
    assert body["workspaceId"] == WORKSPACE_ID
    assert body["name"] == "seg-7"
    assert body["definition"]["entryNode"]["type"] == "Manual"
    assert "id" not in body


def test_upsert_manual_segment_updates_existing(stub_workspace, monkeypatch):
    existing = "fea51159-3e5a-42a5-a969-9e3356f2937f"
    _install_fake_client(
        monkeypatch,
        _FakeResponse(200, {"id": existing, "name": "seg-7-renamed"}),
    )

    df_id = dittofeed_client.upsert_manual_segment(
        "seg-7-renamed", existing_id=existing
    )

    assert df_id == existing
    body = _FakeClient.last["json"]
    assert body["id"] == existing


def test_upsert_manual_segment_raises_on_http_error(stub_workspace, monkeypatch):
    _install_fake_client(
        monkeypatch, _FakeResponse(500, {}, text="boom")
    )

    with pytest.raises(dittofeed_client.DittofeedError):
        dittofeed_client.upsert_manual_segment("seg-bad")


def test_delete_segment_sends_workspace_and_id(stub_workspace, monkeypatch):
    _install_fake_client(monkeypatch, _FakeResponse(204))

    dittofeed_client.delete_segment("abc-123")

    assert _FakeClient.last["method"] == "DELETE"
    assert _FakeClient.last["url"].endswith("/api/segments/")
    assert _FakeClient.last["json"] == {
        "workspaceId": WORKSPACE_ID,
        "id": "abc-123",
    }


def test_delete_segment_swallows_404(stub_workspace, monkeypatch):
    _install_fake_client(monkeypatch, _FakeResponse(404, {}, text="not found"))

    dittofeed_client.delete_segment("abc-123")  # no raise


def test_update_manual_segment_members_skips_when_empty(stub_workspace, monkeypatch):
    _FakeClient.last = {"method": "SENTINEL"}
    _install_fake_client(monkeypatch, _FakeResponse(200))

    dittofeed_client.update_manual_segment_members("abc-123", [])

    assert _FakeClient.last == {"method": "SENTINEL"}


def test_update_manual_segment_members_posts_payload(stub_workspace, monkeypatch):
    _FakeClient.last = {}
    _install_fake_client(monkeypatch, _FakeResponse(200))

    dittofeed_client.update_manual_segment_members(
        "abc-123", ["u1", "u2"], append=True
    )

    body = _FakeClient.last["json"]
    assert _FakeClient.last["method"] == "POST"
    assert _FakeClient.last["url"].endswith(
        "/api/segments/manual-segment/update"
    )
    assert body == {
        "workspaceId": WORKSPACE_ID,
        "segmentId": "abc-123",
        "userIds": ["u1", "u2"],
        "append": True,
    }


def test_update_manual_segment_members_raises_on_http_error(
    stub_workspace, monkeypatch
):
    _install_fake_client(monkeypatch, _FakeResponse(500, {}, text="workflow failed"))

    with pytest.raises(dittofeed_client.DittofeedError):
        dittofeed_client.update_manual_segment_members("abc", ["u1"])
