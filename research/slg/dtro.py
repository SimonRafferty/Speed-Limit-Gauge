"""DfT D-TRO consumer client (OAuth2 client credentials) and speed-limit parser."""
import os
import time

import requests
from dotenv import load_dotenv

from slg.paths import ROOT

BASES = {
    "integration": "https://dtro-integration.dft.gov.uk/v1",
    "production": "https://dtro.dft.gov.uk/v1",
}
SPEED_TYPES = ("speedLimitValueBased", "speedLimitProfileBased")


class DtroClient:
    def __init__(self, client_id: str, client_secret: str, env: str = "integration", session=requests):
        self.base = BASES[env]
        self._auth = (client_id, client_secret)
        self._session = session
        self._token = None
        self._expires = 0.0

    def token(self) -> str:
        # Refresh a minute early so a long download never starts with a dying token.
        if self._token is None or time.time() > self._expires - 60:
            r = self._session.post(f"{self.base}/oauth-generator", auth=self._auth,
                                   data={"grant_type": "client_credentials"}, timeout=30)
            r.raise_for_status()
            body = r.json()
            self._token = body["access_token"]
            self._expires = time.time() + float(body.get("expires_in", 1799))
        return self._token

    def _get(self, path: str):
        r = self._session.get(f"{self.base}{path}",
                              headers={"Authorization": f"Bearer {self.token()}"}, timeout=60)
        r.raise_for_status()
        return r.json()

    def all_records_url(self) -> str:
        """Signed URL (valid 60 min) to a CSV of every published D-TRO."""
        return self._get("/dtros/all")

    def get(self, dtro_id: str) -> dict:
        return self._get(f"/dtros/{dtro_id}")


def from_env(session=requests) -> DtroClient | None:
    load_dotenv(ROOT / ".env")
    cid, secret = os.getenv("DTRO_CLIENT_ID"), os.getenv("DTRO_CLIENT_SECRET")
    if not cid or not secret:
        return None
    return DtroClient(cid, secret, os.getenv("DTRO_ENV", "integration"), session)


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def speed_provisions(record: dict) -> list[dict]:
    """One row per speed-limit regulation in a D-TRO record (schema v3 and v5 shapes)."""
    source = record.get("data", {}).get("source", {})
    out = []
    for prov in source.get("provision", []):
        for reg in prov.get("regulation", []):
            rtype = reg.get("regulationType") or reg.get("generalRegulation", {}).get("regulationType")
            if rtype not in SPEED_TYPES:
                continue
            detail = reg.get(rtype, {})
            out.append({
                "dtro_id": record.get("id"),
                "schema_version": record.get("schemaVersion"),
                "provision_ref": prov.get("reference"),
                "action": prov.get("actionType"),
                "regulation_type": rtype,
                "limit_type": detail.get("type"),
                "mph": detail.get("mphValue"),
                "nature": detail.get("nature"),
                "is_dynamic": reg.get("isDynamic"),
                "geometries": [s for s in _strings(prov.get("regulatedPlace", []))
                               if s.startswith("SRID=")],
            })
    return out
