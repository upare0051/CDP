from app.services import dittofeed_client


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
