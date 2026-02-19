import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class GrafanaError(Exception):
    pass


class GrafanaService:
    def __init__(self, url: str, user: str, password: str) -> None:
        self.base_url = url.rstrip("/")
        self._auth = (user, password)

    def _client(self, org_id: int | None = None) -> httpx.AsyncClient:
        headers: dict[str, str] = {}
        if org_id is not None:
            headers["X-Grafana-Org-Id"] = str(org_id)
        return httpx.AsyncClient(
            base_url=self.base_url,
            auth=self._auth,
            headers=headers,
            timeout=10.0,
        )

    # ------------------------------------------------------------------
    # Organizations
    # ------------------------------------------------------------------

    async def create_organization(self, name: str) -> int:
        """Create a new Grafana organization and return its ID."""
        try:
            async with self._client() as client:
                resp = await client.post("/api/orgs", json={"name": name})
                if resp.status_code not in (200, 201):
                    raise GrafanaError(
                        f"Failed to create organization: {resp.text}"
                    )
                return resp.json()["orgId"]
        except GrafanaError:
            raise
        except httpx.RequestError:
            raise GrafanaError(
                f"Cannot reach Grafana at {self.base_url}. "
                "Check that the service is running and GRAFANA_URL is correct."
            )

    async def get_organization_by_name(self, name: str) -> dict[str, Any] | None:
        """Return the org dict or None if not found."""
        try:
            async with self._client() as client:
                resp = await client.get(f"/api/orgs/name/{name}")
                if resp.status_code == 404:
                    return None
                if resp.status_code != 200:
                    raise GrafanaError(f"Failed to look up organization: {resp.text}")
                return resp.json()
        except GrafanaError:
            raise
        except httpx.RequestError:
            raise GrafanaError(
                f"Cannot reach Grafana at {self.base_url}. "
                "Check that the service is running and GRAFANA_URL is correct."
            )

    async def list_organizations(self) -> list[dict[str, Any]]:
        """Return all organizations except the built-in 'Main Org.'."""
        try:
            async with self._client() as client:
                resp = await client.get("/api/orgs")
                if resp.status_code != 200:
                    raise GrafanaError(f"Failed to list organizations: {resp.text}")
                orgs: list[dict[str, Any]] = resp.json()
                return [o for o in orgs if o["name"] != "Main Org."]
        except GrafanaError:
            raise
        except httpx.RequestError:
            raise GrafanaError(
                f"Cannot reach Grafana at {self.base_url}. "
                "Check that the service is running and GRAFANA_URL is correct."
            )

    async def delete_organization(self, org_id: int) -> None:
        """Delete an organization by ID."""
        try:
            async with self._client() as client:
                resp = await client.delete(f"/api/orgs/{org_id}")
                if resp.status_code not in (200, 404):
                    raise GrafanaError(
                        f"Failed to delete organization {org_id}: {resp.text}"
                    )
        except GrafanaError:
            raise
        except httpx.RequestError:
            raise GrafanaError(
                f"Cannot reach Grafana at {self.base_url}. "
                "Check that the service is running and GRAFANA_URL is correct."
            )

    # ------------------------------------------------------------------
    # Datasources
    # ------------------------------------------------------------------

    async def add_datasources(self, org_id: int, project_name: str) -> None:
        """Add Prometheus, Loki (with X-Scope-OrgID header), and Tempo datasources."""
        datasources = [
            {
                "name": "Prometheus",
                "type": "prometheus",
                "url": "http://prometheus:9090",
                "access": "proxy",
                "isDefault": True,
            },
            {
                "name": "Loki",
                "type": "loki",
                "url": "http://loki:3100",
                "access": "proxy",
                "jsonData": {
                    "httpHeaderName1": "X-Scope-OrgID",
                },
                "secureJsonData": {
                    "httpHeaderValue1": project_name,
                },
            },
            {
                "name": "Tempo",
                "type": "tempo",
                "url": "http://tempo:3200",
                "access": "proxy",
            },
        ]
        try:
            async with self._client(org_id) as client:
                for ds in datasources:
                    resp = await client.post("/api/datasources", json=ds)
                    if resp.status_code not in (200, 201, 409):
                        raise GrafanaError(
                            f"Failed to add datasource '{ds['name']}': {resp.text}"
                        )
        except GrafanaError:
            raise
        except httpx.RequestError:
            raise GrafanaError(
                f"Cannot reach Grafana at {self.base_url}. "
                "Check that the service is running and GRAFANA_URL is correct."
            )

    # ------------------------------------------------------------------
    # Folders
    # ------------------------------------------------------------------

    async def create_folder(self, org_id: int, project_name: str) -> None:
        """Create a dashboard folder named after the project."""
        try:
            async with self._client(org_id) as client:
                resp = await client.post(
                    "/api/folders",
                    json={"title": project_name},
                )
                if resp.status_code not in (200, 201, 412):
                    raise GrafanaError(f"Failed to create folder: {resp.text}")
        except GrafanaError:
            raise
        except httpx.RequestError:
            raise GrafanaError(
                f"Cannot reach Grafana at {self.base_url}. "
                "Check that the service is running and GRAFANA_URL is correct."
            )

    # ------------------------------------------------------------------
    # Alerting
    # ------------------------------------------------------------------

    async def setup_alerting(
        self, org_id: int, bot_token: str, chat_id: str
    ) -> None:
        """Configure Telegram contact point + routing policy for the org."""
        try:
            async with self._client(org_id) as client:
                cp_resp = await client.post(
                    "/api/v1/provisioning/contact-points",
                    json={
                        "name": "Telegram",
                        "type": "telegram",
                        "settings": {
                            "bottoken": bot_token,
                            "chatid": str(chat_id),
                        },
                    },
                )
                if cp_resp.status_code not in (200, 201, 202):
                    raise GrafanaError(
                        f"Failed to create Telegram contact point: {cp_resp.text}"
                    )

                policy_resp = await client.put(
                    "/api/v1/provisioning/policies",
                    json={
                        "receiver": "Telegram",
                        "group_by": ["alertname"],
                        "group_wait": "30s",
                        "group_interval": "5m",
                        "repeat_interval": "4h",
                    },
                )
                if policy_resp.status_code not in (200, 202):
                    raise GrafanaError(
                        f"Failed to set notification policy: {policy_resp.text}"
                    )
        except GrafanaError:
            raise
        except httpx.RequestError:
            raise GrafanaError(
                f"Cannot reach Grafana at {self.base_url}. "
                "Check that the service is running and GRAFANA_URL is correct."
            )
