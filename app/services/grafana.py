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
        """Create a new Grafana organization and return its ID.

        Raises GrafanaError if the org already exists or the request fails.
        """
        try:
            async with self._client() as client:
                check = await client.get(f"/api/orgs/name/{name}")
                if check.status_code == 200:
                    raise GrafanaError(f"Organization '{name}' already exists.")

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
                "jsonData": {"timeInterval": "15s"},
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
                    # 409 = datasource with this name already exists in the org
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
        uid = project_name.lower().replace(" ", "-")[:40]
        try:
            async with self._client(org_id) as client:
                resp = await client.post(
                    "/api/folders",
                    json={"title": project_name, "uid": uid},
                )
                # 412 = folder with this uid already exists
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

    # ------------------------------------------------------------------
    # Alerting
    # ------------------------------------------------------------------

    async def _create_temp_token(self, org_id: int) -> tuple[int, str]:
        """Create a temporary Admin service account + token in org_id.

        Returns (service_account_id, token). The token is scoped to the org
        so provisioning API calls made with it need no X-Grafana-Org-Id header.
        """
        logger.debug("Creating temp service account for org_id=%s", org_id)
        async with self._client(org_id) as client:
            sa_payload = {"name": "grafana-bot-setup", "role": "Admin", "isDisabled": False}
            logger.debug("POST /api/serviceaccounts payload: %s", sa_payload)
            sa_resp = await client.post("/api/serviceaccounts", json=sa_payload)
            logger.debug(
                "POST /api/serviceaccounts -> status=%s body=%s",
                sa_resp.status_code, sa_resp.text,
            )
            if sa_resp.status_code not in (200, 201):
                logger.error(
                    "Failed to create service account: status=%s body=%s",
                    sa_resp.status_code, sa_resp.text,
                )
                raise GrafanaError(
                    f"Failed to create service account: {sa_resp.text}"
                )
            sa_id: int = sa_resp.json()["id"]
            logger.debug("Service account created: id=%s", sa_id)

            tok_payload = {"name": "grafana-bot-setup-token"}
            logger.debug("POST /api/serviceaccounts/%s/tokens payload: %s", sa_id, tok_payload)
            tok_resp = await client.post(
                f"/api/serviceaccounts/{sa_id}/tokens",
                json=tok_payload,
            )
            logger.debug(
                "POST /api/serviceaccounts/%s/tokens -> status=%s body=%s",
                sa_id, tok_resp.status_code, tok_resp.text,
            )
            if tok_resp.status_code not in (200, 201):
                logger.error(
                    "Failed to create service account token: status=%s body=%s",
                    tok_resp.status_code, tok_resp.text,
                )
                raise GrafanaError(
                    f"Failed to create service account token: {tok_resp.text}"
                )
            token: str = tok_resp.json()["key"]
            logger.debug("Service account token created successfully")

        return sa_id, token

    async def _delete_service_account(self, org_id: int, sa_id: int) -> None:
        async with self._client(org_id) as client:
            await client.delete(f"/api/serviceaccounts/{sa_id}")

    def _token_client(self, token: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )

    async def setup_alerting(
        self, org_id: int, bot_token: str, chat_id: str
    ) -> None:
        """Configure Telegram alerting for the org via Alertmanager config API.

        Uses admin basic auth with X-Grafana-Org-Id — the super-admin can reach
        the Grafana-managed Alertmanager for any org, which service-account tokens
        cannot do for freshly created orgs.
        """
        am_payload = {
            "alertmanager_config": {
                "route": {
                    "receiver": "Telegram",
                    "group_by": ["alertname"],
                    "group_wait": "30s",
                    "group_interval": "5m",
                    "repeat_interval": "4h",
                },
                "receivers": [
                    {
                        "name": "Telegram",
                        "grafana_managed_receiver_configs": [
                            {
                                "name": "Telegram",
                                "type": "telegram",
                                "settings": {
                                    "bottoken": bot_token,
                                    "chatid": str(chat_id),
                                },
                            }
                        ],
                    }
                ],
            }
        }
        try:
            async with self._client(org_id) as client:
                logger.debug(
                    "POST /api/alertmanager/grafana/config/api/v1/alerts org_id=%s payload: %s",
                    org_id,
                    str(am_payload).replace(bot_token, "***"),
                )
                am_resp = await client.post(
                    "/api/alertmanager/grafana/config/api/v1/alerts",
                    json=am_payload,
                )
                logger.debug(
                    "POST /api/alertmanager/grafana/config/api/v1/alerts -> status=%s body=%s",
                    am_resp.status_code, am_resp.text,
                )
                if am_resp.status_code not in (200, 201, 202):
                    logger.error(
                        "Failed to configure Alertmanager: status=%s body=%s",
                        am_resp.status_code, am_resp.text,
                    )
                    raise GrafanaError(
                        f"Failed to configure Alertmanager: {am_resp.text}"
                    )
        except GrafanaError:
            raise
        except httpx.RequestError:
            raise GrafanaError(
                f"Cannot reach Grafana at {self.base_url}. "
                "Check that the service is running and GRAFANA_URL is correct."
            )
