"""Orchestrator API client with configurable request timeout."""

import json
import logging
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30  # seconds


class OrchestratorClient:
    """HTTP client for the Agent Orchestrator API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        if timeout < 1:
            raise ValueError("timeout must be >= 1 second")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[Dict] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Make an HTTP request with configurable per-call timeout."""
        url = f"{self.base_url}/api/v2{path}"
        data = json.dumps(body).encode() if body else None
        actual_timeout = timeout if timeout is not None else self.timeout

        req = Request(url, data=data, headers=self._headers(), method=method)
        try:
            with urlopen(req, timeout=actual_timeout) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            error_body = e.read().decode(errors="replace")
            logger.error("HTTP %d on %s %s: %s", e.code, method, path, error_body[:200])
            raise
        except URLError as e:
            logger.error("Connection error on %s %s: %s", method, path, e.reason)
            raise

    def list_agents(
        self, status: Optional[str] = None, timeout: Optional[int] = None
    ) -> List[Dict]:
        return self._request("GET", "/agents", timeout=timeout).get("agents", [])

    def get_agent(self, agent_id: str, timeout: Optional[int] = None) -> Optional[Dict]:
        return self._request("GET", f"/agents/{agent_id}", timeout=timeout)

    def register_agent(
        self,
        name: str,
        agent_type: str,
        config: Optional[Dict] = None,
        timeout: Optional[int] = None,
    ) -> Dict:
        body = {"name": name, "agent_type": agent_type, "config": config or {}}
        return self._request("POST", "/agents", body, timeout=timeout)

    def delete_agent(self, agent_id: str, timeout: Optional[int] = None) -> Dict:
        return self._request("DELETE", f"/agents/{agent_id}", timeout=timeout)

    def start_agent(self, agent_id: str, timeout: Optional[int] = None) -> Dict:
        return self._request("POST", f"/agents/{agent_id}/start", timeout=timeout)

    def stop_agent(self, agent_id: str, timeout: Optional[int] = None) -> Dict:
        return self._request("POST", f"/agents/{agent_id}/stop", timeout=timeout)

    def health(self, timeout: Optional[int] = None) -> Dict:
        return self._request("GET", "", timeout=timeout)
