from typing import Any

import httpx


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
        async with self._client(org_id) as client:
            sa_resp = await client.post(
                "/api/serviceaccounts",
                json={"name": "grafana-bot-setup", "role": "Admin", "isDisabled": False},
            )
            if sa_resp.status_code not in (200, 201):
                raise GrafanaError(
                    f"Failed to create service account: {sa_resp.text}"
                )
            sa_id: int = sa_resp.json()["id"]

            tok_resp = await client.post(
                f"/api/serviceaccounts/{sa_id}/tokens",
                json={"name": "grafana-bot-setup-token"},
            )
            if tok_resp.status_code not in (200, 201):
                raise GrafanaError(
                    f"Failed to create service account token: {tok_resp.text}"
                )
            token: str = tok_resp.json()["key"]

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
        """Configure Telegram contact point + routing policy for the org.

        Creates a temporary service account token scoped to the org so that
        the provisioning API calls carry the correct org context without
        relying on X-Grafana-Org-Id (which the provisioning API ignores).
        """
        try:
            sa_id, token = await self._create_temp_token(org_id)
        except httpx.RequestError:
            raise GrafanaError(
                f"Cannot reach Grafana at {self.base_url}. "
                "Check that the service is running and GRAFANA_URL is correct."
            )

        try:
            async with self._token_client(token) as client:
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
        finally:
            await self._delete_service_account(org_id, sa_id)
