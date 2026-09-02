"""
CNC302 Лаб 7 — GraphQL давхарга (өөрсдийн REGISTRY + InfluxDB 3 дээр)

Хоёр эх сурвалжийг нэг схемд нэгтгэнэ:
  1. `registry` (Лаб 2, FastAPI, :8090) — төхөөрөмж, firmware, OTA тараалт
  2. `influxdb` (:8181, SQL)            — цаг цувааны хэмжилт

ThingsBoard энд БАЙХГҮЙ. Шалтгаан нь зөвхөн санах ой биш (Pi 3B-д 1 GB):
худалдааны платформ нь provisioning ба API-г хар хайрцаг болгодог. Бид
Лаб 2-т бүртгэлээ өөрсдөө бичсэн тул одоо түүн дээр GraphQL давхарга
барихад юу ч нуугдахгүй. (ThingsBoard-ыг харьцуулах хүсвэл сонголтот
overlay: `docker compose -f docker-compose.yml -f docker-compose.tb.yml
--profile tb up -d`. Энэ кодод ХЭРЭГГҮЙ.)

Гурван давхарга:
  1. REST клиент      — registry, InfluxDB рүү хандана
  2. GraphQL схем     — нэг хүсэлтээр олон эх сурвалжаас өгөгдөл нэгтгэнэ
  3. Эрхийн шалгалт   — OIDC токен + RBAC үүрэг

  http://<laptop>:8000/graphql   — GraphiQL тоглоомын талбар
  http://<laptop>:8000/health    — эрүүл мэндийн шалгалт

⚠ Байршил: энэ үйлчилгээ ҮҮЛНИЙ давхаргад (зөөврийн компьютер) ажиллана.
  Pi 3B нь зөвхөн ирмэгийн үүрэгтэй.

⚠ ОЮУТНЫ ДААЛГАВАР: `# TODO(оюутан)` гэсэн хэсгүүдийг бөглөнө.
⚠ Энэ файлд ХОЁР САНААТАЙ ЭМЗЭГ БАЙДАЛ бий. Тэмдэглэгээг нь хайж ол.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import httpx
import strawberry
from fastapi import Depends, FastAPI, Header, HTTPException
from strawberry.fastapi import GraphQLRouter

# Хостоос: http://localhost:8090 / compose сүлжээн дотроос: http://registry:8090
REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://localhost:8090")
INFLUX_URL = os.environ.get("INFLUX_URL", "http://localhost:8181")
INFLUX_DB = os.environ.get("INFLUX_DB", "cnc302")
OIDC_ISSUER = os.environ.get("OIDC_ISSUER", "http://dex:5556/dex")

# UNS-ийн байрлал — тушаалын сэдэв үүсгэхэд хэрэгтэй (Лаб 3)
SITE = os.environ.get("SITE", "shutis")
AREA = os.environ.get("AREA", "mhts")
LINE = os.environ.get("LINE", "lab")

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


# Zero Trust: токенгүй хүсэлт НЭГ Ч үүрэггүй. `whoami` л ажиллана,
# өгөгдлийн талбар бүр татгалзана.
ANONYMOUS = Principal(subject="anonymous", roles=[])


def decode_token(token: str) -> Principal:
    """
    OIDC токеныг задлан шинжилнэ.

    # ⚠ САНААТАЙ ЭМЗЭГ БАЙДАЛ (Лаб 7-д засна) #1:
    #   гарын үсгийг ШАЛГАХГҮЙ, `exp`-ийг ч шалгахгүй. Хэн ч дурын
    #   claims бичээд admin болно. Алхам 4-т үүнийг халдлагаар нотолж,
    #   дараа нь заслаа.
    #
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


# ─────────────────────── Registry клиент (Лаб 2) ───────────────────────

class RegistryClient:
    """
    Лаб 2-ын бүртгэлийн REST клиент. Токен, session хэрэггүй — энэ бол
    лабораторийн энгийн байдал бөгөөд Лаб 7-ын шүүмжлэлийн сэдэв:
    дотоод үйлчилгээ хоорондын танилт БАЙХГҮЙ (Zero Trust зөрчсөн).
    """

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    async def get(self, path: str, **params):
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{self.base}{path}", params=params)
            r.raise_for_status()
            return r.json()


registry = RegistryClient(REGISTRY_URL)


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
class Firmware:
    id: str
    version: str
    size: int
    sha256: str


@strawberry.type
class Device:
    id: str
    name: str
    type: str
    label: Optional[str] = None
    state: Optional[str] = None          # provisioned | active | revoked
    fw_version: Optional[str] = None
    last_seen: Optional[int] = None

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


def to_device(d: dict) -> Device:
    """registry-ийн JSON мөрийг GraphQL төрөл рүү."""
    return Device(id=str(d.get("id", "")), name=str(d.get("id", "")),
                  type=str(d.get("label") or "device"),
                  label=d.get("label"), state=d.get("state"),
                  fw_version=d.get("fw_version"), last_seen=d.get("last_seen"))


@strawberry.type
class Query:
    @strawberry.field
    async def whoami(self, info: strawberry.Info) -> str:
        p: Principal = info.context["principal"]
        return (f"subject={p.subject} roles={','.join(p.roles)} "
                f"tenant={p.tenant} perms={','.join(sorted(p.permissions))}")

    @strawberry.field
    async def devices(self, info: strawberry.Info, limit: int = 50,
                      state: Optional[str] = None) -> list[Device]:
        p: Principal = info.context["principal"]
        p.require("device:read")
        params = {"limit": min(limit, 200)}
        if state:
            params["state"] = state
        data = await registry.get("/devices", **params)
        return [to_device(d) for d in data.get("devices", [])]

    @strawberry.field
    async def device(self, info: strawberry.Info, name: str) -> Optional[Device]:
        p: Principal = info.context["principal"]
        p.require("device:read")
        try:
            data = await registry.get("/devices", limit=500)
        except httpx.HTTPError:
            return None
        # Шүүлтийг ЭНД хийж байгаа нь санамсаргүй биш: бүртгэлийн ID-г
        # SQL/URL-д залгахгүй тул тарилгын гадаргуу багасна.
        for d in data.get("devices", []):
            if str(d.get("id")) == name:
                return to_device(d)
        return None

    @strawberry.field
    async def firmware(self, info: strawberry.Info) -> list[Firmware]:
        """Бүртгэлд байршуулсан firmware хувилбарууд (Лаб 2-ын OTA)."""
        p: Principal = info.context["principal"]
        p.require("device:read")
        data = await registry.get("/firmware")
        return [Firmware(id=str(f.get("id", "")), version=str(f.get("version", "")),
                         size=int(f.get("size", 0)), sha256=str(f.get("sha256", "")))
                for f in data.get("firmware", [])]

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
        # TODO(оюутан): тушаалыг UNS-ийн cmd сэдэв рүү нийтлэх.
        #   Топик: cnc302/{SITE}/{AREA}/{LINE}/{device}/cmd
        #   paho-mqtt-ээр EMQX (үүл) рүү нийтэлбэл гүүр Pi рүү дамжуулна.
        topic = f"cnc302/{SITE}/{AREA}/{LINE}/{device}/cmd"
        return (f"'{command}' тушаалыг {topic} руу илгээхээр хүлээн авлаа "
                f"(хэрэгжүүлээгүй — оюутны даалгавар)")


# ⚠ САНААТАЙ ЭМЗЭГ БАЙДАЛ (Лаб 7-д засна) #2:
#   introspection НЭЭЛТТЭЙ, асуулгын гүн/нийлмэл байдлын ХЯЗГААР БАЙХГҮЙ.
#   Нэг хүсэлтэд 200 давхар нэрлэсэн (alias) талбар бичээд серверийг
#   ачаалж болно — REST-д боломжгүй DoS вектор.
#   Засварын чиглэл: strawberry-ийн QueryDepthLimiter / cost analysis
#   өргөтгөл нэмэх, introspection-ыг зөвхөн нэвтэрсэн хэрэглэгчид нээх.
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
        for name, url in (("registry", f"{REGISTRY_URL}/health"),
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
    data = await registry.get("/devices", limit=min(limit, 200))
    return {"count": len(data.get("devices", [])),
            "devices": [{"id": d["id"], "name": d["id"],
                         "state": d.get("state")}
                        for d in data.get("devices", [])]}
