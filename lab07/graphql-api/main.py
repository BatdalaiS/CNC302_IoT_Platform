"""
CNC302 Лаб 7 — GraphQL давхарга (ThingsBoard REST + InfluxDB 3 дээр)

ThingsBoard CE нь GraphQL API-гүй. Тиймээс бид түүнийг өөрсдөө барина.
Энэ нь REST ба GraphQL-ийн ялгааг ЗОХИОН БҮТЭЭХ замаар ойлгох боломж өгнө.

Гурван давхарга:
  1. REST клиент      — ThingsBoard, InfluxDB рүү хандана
  2. GraphQL схем     — нэг хүсэлтээр олон эх сурвалжаас өгөгдөл нэгтгэнэ
  3. Эрхийн шалгалт   — OIDC токен + RBAC үүрэг

  http://<pi>:8000/graphql   — GraphiQL тоглоомын талбар
  http://<pi>:8000/health    — эрүүл мэндийн шалгалт

⚠ ОЮУТНЫ ДААЛГАВАР: `# TODO(оюутан)` гэсэн хэсгүүдийг бөглөнө.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional

import httpx
import strawberry
from fastapi import Depends, FastAPI, Header, HTTPException
from strawberry.fastapi import GraphQLRouter

TB_URL = os.environ.get("TB_URL", "http://thingsboard:9090")
TB_USER = os.environ.get("TB_USER", "tenant@thingsboard.org")
TB_PASSWORD = os.environ.get("TB_PASSWORD", "tenant")
INFLUX_URL = os.environ.get("INFLUX_URL", "http://influxdb:8181")
INFLUX_DB = os.environ.get("INFLUX_DB", "cnc302")
OIDC_ISSUER = os.environ.get("OIDC_ISSUER", "http://dex:5556/dex")

# ─────────────────────────── RBAC ───────────────────────────
# Үүрэг → зөвшөөрөгдсөн үйлдлүүд. Лаб 7-д үүнийг өргөтгөнө.
ROLES: dict[str, set[str]] = {
    "viewer": {"device:read", "telemetry:read"},
    "operator": {"device:read", "telemetry:read", "device:command"},
    "admin": {"device:read", "telemetry:read", "device:command",
              "device:write", "device:delete"},
}


@dataclass
class Principal:
    """Хүсэлт гаргаж буй этгээд."""
    subject: str
    roles: list[str]
    tenant: str = "default"

    @property
    def permissions(self) -> set[str]:
        out: set[str] = set()
        for r in self.roles:
            out |= ROLES.get(r, set())
        return out

    def require(self, perm: str) -> None:
        if perm not in self.permissions:
            raise PermissionError(
                f"'{perm}' эрх байхгүй. Таны үүрэг: {self.roles}")


ANONYMOUS = Principal(subject="anonymous", roles=["viewer"])


def decode_token(token: str) -> Principal:
    """
    OIDC токеныг задлан шинжилнэ.

    ⚠ ЛАБОРАТОРИЙН ХУВИЛБАР: гарын үсгийг ШАЛГАХГҮЙ.
    Энэ бол зориудын эмзэг байдал — Алхам 4-т та үүнийг халдлагаар
    ашиглаж үзээд, дараа нь заслаа.

    # TODO(оюутан): Dex-ийн JWKS-ээр гарын үсгийг шалгах
    #   from jose import jwt
    #   jwks = httpx.get(f"{OIDC_ISSUER}/keys").json()
    #   claims = jwt.decode(token, jwks, algorithms=["RS256"],
    #                       audience="cnc302", issuer=OIDC_ISSUER)
    """
    from jose import jwt
    claims = jwt.get_unverified_claims(token)   # ← ЭМЗЭГ
    roles = claims.get("groups") or claims.get("roles") or ["viewer"]
    if isinstance(roles, str):
        roles = [roles]
    return Principal(subject=claims.get("sub", "unknown"), roles=list(roles),
                     tenant=claims.get("tenant", "default"))


async def get_principal(authorization: Optional[str] = Header(None)) -> Principal:
    if not authorization:
        return ANONYMOUS
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Bearer токен шаардлагатай")
    try:
        return decode_token(authorization.split(" ", 1)[1])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(401, f"Токен буруу: {exc}") from exc


# ─────────────────────── ThingsBoard клиент ───────────────────────

class TBClient:
    def __init__(self) -> None:
        self._token: str | None = None
        self._exp = 0.0

    async def token(self, client: httpx.AsyncClient) -> str:
        if self._token and time.time() < self._exp:
            return self._token
        r = await client.post(f"{TB_URL}/api/auth/login",
                              json={"username": TB_USER, "password": TB_PASSWORD})
        r.raise_for_status()
        self._token = r.json()["token"]
        self._exp = time.time() + 300
        return self._token

    async def get(self, path: str, **params):
        async with httpx.AsyncClient(timeout=15) as c:
            t = await self.token(c)
            r = await c.get(f"{TB_URL}{path}",
                            headers={"X-Authorization": f"Bearer {t}"},
                            params=params)
            r.raise_for_status()
            return r.json()


tb = TBClient()


async def influx_sql(q: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{INFLUX_URL}/api/v3/query_sql",
                         json={"db": INFLUX_DB, "q": q, "format": "json"})
        r.raise_for_status()
        return r.json()


# ─────────────────────────── GraphQL схем ───────────────────────────

@strawberry.type
class Reading:
    time: str
    device: str
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    vibration_rms: Optional[float] = None


@strawberry.type
class Device:
    id: str
    name: str
    type: str
    label: Optional[str] = None

    @strawberry.field
    async def readings(self, info: strawberry.Info, limit: int = 20) -> list[Reading]:
        """
        Энэ бол GraphQL-ийн гол давуу тал: клиент нэг хүсэлтээр
        төхөөрөмж + түүний хэмжилтийг зэрэг авна. REST дээр 1 + N хүсэлт.
        """
        p: Principal = info.context["principal"]
        p.require("telemetry:read")
        rows = await influx_sql(
            f"SELECT time, device, temperature, humidity, vibration_rms "
            f"FROM telemetry WHERE device = '{self.name}' "
            f"ORDER BY time DESC LIMIT {min(limit, 500)}")
        return [Reading(time=str(r.get("time")), device=str(r.get("device")),
                        temperature=r.get("temperature"),
                        humidity=r.get("humidity"),
                        vibration_rms=r.get("vibration_rms")) for r in rows]


@strawberry.type
class Query:
    @strawberry.field
    async def whoami(self, info: strawberry.Info) -> str:
        p: Principal = info.context["principal"]
        return (f"subject={p.subject} roles={','.join(p.roles)} "
                f"tenant={p.tenant} perms={','.join(sorted(p.permissions))}")

    @strawberry.field
    async def devices(self, info: strawberry.Info, limit: int = 50) -> list[Device]:
        p: Principal = info.context["principal"]
        p.require("device:read")
        data = await tb.get("/api/tenant/devices", pageSize=min(limit, 200), page=0)
        return [Device(id=d["id"]["id"], name=d["name"], type=d.get("type", ""),
                       label=d.get("label")) for d in data.get("data", [])]

    @strawberry.field
    async def device(self, info: strawberry.Info, name: str) -> Optional[Device]:
        p: Principal = info.context["principal"]
        p.require("device:read")
        try:
            d = await tb.get("/api/tenant/devices", deviceName=name)
        except httpx.HTTPStatusError:
            return None
        return Device(id=d["id"]["id"], name=d["name"], type=d.get("type", ""),
                      label=d.get("label"))

    @strawberry.field
    async def anomalies(self, info: strawberry.Info, hours: int = 24, limit: int = 100) -> list[Reading]:
        """Лаб 6-ийн ирмэгийн дүгнэлтээр илэрсэн гажлууд."""
        p: Principal = info.context["principal"]
        p.require("telemetry:read")
        rows = await influx_sql(
            f"SELECT time, device, temperature, vibration_rms FROM telemetry "
            f"WHERE vibration_rms > 1.5 "
            f"AND time > now() - INTERVAL '{int(hours)} hours' "
            f"ORDER BY time DESC LIMIT {min(limit, 500)}")
        return [Reading(time=str(r.get("time")), device=str(r.get("device")),
                        temperature=r.get("temperature"),
                        vibration_rms=r.get("vibration_rms")) for r in rows]

    # TODO(оюутан): `deviceStats(device: String!, hours: Int!)` талбар нэмнэ
    #   — дундаж, хамгийн их, хамгийн бага температур, дээжийн тоог буцаана.
    #   InfluxDB-д нэгтгэлийг хийлгэнэ (SQL-ийн avg/min/max), Python дээр биш.


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def send_command(self, info: strawberry.Info, device: str, command: str) -> str:
        p: Principal = info.context["principal"]
        p.require("device:command")     # ← viewer энд татгалзана
        # TODO(оюутан): ThingsBoard-ын RPC API-гаар тушаал илгээх
        #   POST /api/plugins/rpc/oneway/{deviceId}
        return f"'{command}' тушаалыг {device}-д илгээхээр хүлээн авлаа " \
               f"(хэрэгжүүлээгүй — оюутны даалгавар)"


schema = strawberry.Schema(query=Query, mutation=Mutation)


async def context_getter(principal: Principal = Depends(get_principal)) -> dict:
    return {"principal": principal}


app = FastAPI(title="CNC302 GraphQL API", version="lab07")
app.include_router(GraphQLRouter(schema, context_getter=context_getter),
                   prefix="/graphql")


@app.get("/health")
async def health() -> dict:
    out = {"status": "ok", "checks": {}}
    async with httpx.AsyncClient(timeout=5) as c:
        for name, url in (("thingsboard", f"{TB_URL}/login"),
                          ("influxdb", f"{INFLUX_URL}/health")):
            try:
                r = await c.get(url)
                out["checks"][name] = r.status_code
            except Exception as exc:  # noqa: BLE001
                out["checks"][name] = str(exc)
                out["status"] = "degraded"
    return out


@app.get("/rest/devices")
async def rest_devices(principal: Principal = Depends(get_principal),
                       limit: int = 50) -> dict:
    """
    REST-ийн адил төгсгөлийн цэг — GraphQL-тэй харьцуулах зорилготой.
    Анхаар: энэ нь ЗӨВХӨН төхөөрөмжийн жагсаалт буцаана. Хэмжилт авахын
    тулд клиент N нэмэлт хүсэлт хийх ёстой (1+N асуудал).
    """
    try:
        principal.require("device:read")
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    data = await tb.get("/api/tenant/devices", pageSize=min(limit, 200), page=0)
    return {"count": len(data.get("data", [])),
            "devices": [{"id": d["id"]["id"], "name": d["name"]}
                        for d in data.get("data", [])]}
