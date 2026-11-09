"""Talks to the engine API (GET/POST /runs). Validates every reply with the shared contracts."""

from typing import Any, List, Optional

import requests
from pydantic import BaseModel, ValidationError

from contracts import Result, Scenario

TIMEOUT_S = 15


class EngineError(Exception):
    """The engine could not be reached, or answered something we cannot use. The message is for the user."""


class Run(BaseModel):
    run_id: str
    status: str  # "running" | "complete"
    created_at: float
    scenario: Scenario
    result: Optional[Result] = None
    rerun_of: Optional[str] = None
    fix: Optional[dict] = None


class Engine:
    def __init__(self, base_url: str, session: Any = None):
        self.base_url = base_url.rstrip("/")
        self.http = session or requests.Session()

    def _call(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
        try:
            resp = self.http.request(method, url, timeout=TIMEOUT_S, **kwargs)
        except requests.RequestException as exc:
            raise EngineError(
                f"Can't reach the engine at {self.base_url} ({type(exc).__name__}). "
                "Start it with `make api` (and the demo shop with `make demo`), or set ENGINE_BASE_URL."
            ) from exc
        if resp.status_code == 404:
            raise EngineError(f"The engine has no {path} (HTTP 404).")
        if resp.status_code >= 400:
            raise EngineError(f"The engine answered {method} {path} with HTTP {resp.status_code}.")
        try:
            return resp.json()
        except ValueError as exc:
            raise EngineError(f"The engine's answer to {method} {path} was not JSON.") from exc

    @staticmethod
    def _run(data: Any) -> Run:
        try:
            return Run.model_validate(data)
        except ValidationError as exc:
            raise EngineError(f"The engine returned a run that does not match the contract: {exc.errors()[0]['loc']}") from exc

    def launch(self, fault: Optional[str] = None) -> Run:
        body = {"fault": fault} if fault else None
        return self._run(self._call("POST", "/runs", json=body))

    def get(self, run_id: str) -> Run:
        return self._run(self._call("GET", f"/runs/{run_id}"))

    def list(self) -> List[Run]:
        data = self._call("GET", "/runs")
        if not isinstance(data, list):
            raise EngineError("The engine's /runs answer was not a list.")
        return [self._run(item) for item in data]
