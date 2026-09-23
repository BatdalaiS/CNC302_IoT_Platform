#!/usr/bin/env python3
"""
CNC302 — ТӨХӨӨРӨМЖИЙН БҮРТГЭЛ ба OTA СЕРВЕР.

Яагаад ThingsBoard биш вэ:
  Raspberry Pi 3B-д 1 GB санах ой байдаг тул ThingsBoard (албан ёсоор ≥ 4 GB)
  ажиллахгүй. Гэхдээ илүү чухал шалтгаан бий: худалдааны платформ нь
  provisioning, identity, OTA-г ХАР ХАЙРЦАГ болгож нуудаг. Энэ ~500 мөр
  код нь тэр гурвыг ИЛ харуулна. Оюутан ThingsBoard-ыг Лаб 2-ын
  сонголтот хэсэгт харьцуулж үзнэ.

Ажиллуулах:
    uvicorn app:app --host 0.0.0.0 --port 8090
    # эсвэл: docker compose --profile core up -d registry

Гол API:
    GET    /health
    POST   /devices                 бөөнөөр бүртгэх (bulk provisioning)
    POST   /devices/claim           төхөөрөмж өөрөө бүртгүүлэх (JIT)
    GET    /devices                 жагсаалт
    DELETE /devices/{id}            хүчингүй болгох (revoke) + идэвхтэй холболтыг таслах
    POST   /firmware                хувилбар байршуулах
    GET    /firmware
    POST   /rollout                 тараалт эхлүүлэх (canary дэмжинэ)
    GET    /rollout/{id}            явц
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

import httpx
import paho.mqtt.client as mqtt
from fastapi import Body, FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from paho.mqtt.enums import CallbackAPIVersion
from pydantic import BaseModel, Field

# ─────────────────────────── Тохиргоо ───────────────────────────
DB_PATH = os.getenv("DB_PATH", "./registry.db")
FW_DIR = Path(os.getenv("FW_DIR", "./firmware"))
EMQX_API = os.getenv("EMQX_API", "http://localhost:18083/api/v5")
EMQX_KEY = os.getenv("EMQX_API_KEY", "")
EMQX_SECRET = os.getenv("EMQX_API_SECRET", "")
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
# EMQX-д нэвтрэлт (authenticator) идэвхтэй үед бүртгэлийн үйлчилгээ өөрөө ч
# нэвтрэх ёстой — эс бөгөөс дахин холбогдоход EMQX татгалзана.
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
SITE = os.getenv("SITE", "shutis")
AREA = os.getenv("AREA", "mhts")
LINE = os.getenv("LINE", "lab")
CHUNK = int(os.getenv("CHUNK_SIZE", "4096"))

FW_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS devices (
          id         TEXT PRIMARY KEY,
          label      TEXT,
          username   TEXT,
          password   TEXT,
          state      TEXT DEFAULT 'provisioned',   -- provisioned|active|revoked
          fw_version TEXT DEFAULT '0.0.0',
          created_at INTEGER,
          last_seen  INTEGER
        );
        CREATE TABLE IF NOT EXISTS firmware (
          id      TEXT PRIMARY KEY,
          version TEXT,
          size    INTEGER,
          sha256  TEXT,
          path    TEXT,
          created_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS rollouts (
          id       TEXT PRIMARY KEY,
          fw_id    TEXT,
          canary   INTEGER,          -- эхний давалгаанд хэдэн хувь
          created_at INTEGER,
          state    TEXT              -- running|halted|done
        );
        CREATE TABLE IF NOT EXISTS rollout_targets (
          rollout_id TEXT,
          device_id  TEXT,
          wave       INTEGER,        -- 0 = canary, 1 = бүгд
          state      TEXT,           -- pending|DOWNLOADING|...|UPDATED|FAILED
          detail     TEXT,
          updated_at INTEGER,
          PRIMARY KEY (rollout_id, device_id)
        );
        """)


# ─────────────────────── EMQX-ийн нэвтрэлт ───────────────────────
# EMQX REST API: /api/v5, HTTP Basic (API key = нэр, secret key = нууц үг).
# Authenticator ID нь "<mechanism>:<backend>"; URL-д ":"-ийг %3A болгоно.
AUTHN_ID = quote("password_based:built_in_database", safe="")


def emqx_auth() -> tuple[str, str] | None:
    return (EMQX_KEY, EMQX_SECRET) if EMQX_KEY and EMQX_SECRET else None


def emqx_add_user(username: str, password: str) -> str:
    """
    EMQX-ийн built-in database authenticator-т хэрэглэгч нэмнэ.
    Түлхүүр байхгүй бол алгасна (Лаб 1-2-ын эхэнд EMQX нээлттэй байна).
    Authenticator-ыг УРЬДЧИЛАН үүсгэсэн байх ёстой (Лаб 2, Алхам 0) —
    эс бөгөөс EMQX 404 буцаана.
    """
    auth = emqx_auth()
    if auth is None:
        return "skipped (EMQX_API_KEY тохируулаагүй)"
    url = f"{EMQX_API}/authentication/{AUTHN_ID}/users"
    try:
        r = httpx.post(url, auth=auth, timeout=8.0,
                       json={"user_id": username, "password": password})
        if r.status_code in (200, 201):
            return "created"
        if r.status_code == 409:
            return "exists"
        if r.status_code == 404:
            return "error 404: authenticator үүсгээгүй (Лаб 2, Алхам 0)"
        return f"error {r.status_code}: {r.text[:120]}"
    except httpx.HTTPError as e:
        return f"unreachable: {e}"


def emqx_del_user(username: str) -> str:
    auth = emqx_auth()
    if auth is None:
        return "skipped"
    url = f"{EMQX_API}/authentication/{AUTHN_ID}/users/{quote(username, safe='')}"
    try:
        r = httpx.delete(url, auth=auth, timeout=8.0)
        if r.status_code in (204, 200):
            return "deleted"
        if r.status_code == 404:
            return "not found"
        return f"error {r.status_code}"
    except httpx.HTTPError as e:
        return f"unreachable: {e}"


def emqx_kick(username: str) -> list[str] | str:
    """
    Хэрэглэгчийг устгах нь зөвхөн ШИНЭ холболтыг хаана — EMQX нэвтрэлтийг
    CONNECT үед л шалгадаг. Аль хэдийн холбогдсон session-ыг таслахын тулд
    тухайн username-тэй бүх клиентийг олж (GET /clients?username=),
    client ID-гаар нь хөөнө (DELETE /clients/{clientid}).
    """
    auth = emqx_auth()
    if auth is None:
        return "skipped"
    try:
        r = httpx.get(f"{EMQX_API}/clients", auth=auth, timeout=8.0,
                      params={"username": username, "limit": 100})
        if r.status_code != 200:
            return f"error {r.status_code}"
        kicked = []
        for cl in r.json().get("data", []):
            cid = cl.get("clientid", "")
            d = httpx.delete(f"{EMQX_API}/clients/{quote(cid, safe='')}",
                             auth=auth, timeout=8.0)
            if d.status_code in (200, 204):
                kicked.append(cid)
        return kicked
    except (httpx.HTTPError, ValueError) as e:
        return f"unreachable: {e}"


# ─────────────────────────── MQTT тал ───────────────────────────
class Bus:
    """OTA-гийн MQTT тал. Төхөөрөмжөөс ирэх төлөв, хэсгийн хүсэлтийг сонсоно."""

    def __init__(self) -> None:
        self.c = mqtt.Client(CallbackAPIVersion.VERSION2,
                             client_id=f"registry-{secrets.token_hex(3)}",
                             protocol=mqtt.MQTTv5)
        if MQTT_USERNAME:
            self.c.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        self.c.on_connect = self._on_connect
        self.c.on_disconnect = self._on_disconnect
        self.c.on_message = self._on_message
        self.connected = False

    def start(self) -> None:
        # connect_async + loop_start: EMQX түр унасан эсвэл хоцорч эхэлсэн ч
        # сүлжээний thread (loop_forever) өөрөө дахин холбогдоно.
        self.c.reconnect_delay_set(min_delay=1, max_delay=30)
        self.c.connect_async(MQTT_HOST, MQTT_PORT, keepalive=45)
        self.c.loop_start()

    # paho-mqtt 2.x, CallbackAPIVersion.VERSION2:
    #   on_connect(client, userdata, flags, reason_code, properties)
    def _on_connect(self, c, u, f, rc, p=None):
        self.connected = rc == 0
        if rc == 0:
            c.subscribe(f"cnc302/{SITE}/+/+/+/ota/state", qos=1)
            c.subscribe(f"cnc302/{SITE}/+/+/+/ota/request", qos=1)
            print(f"[mqtt] холбогдлоо {MQTT_HOST}:{MQTT_PORT}")
        else:
            print(f"[mqtt] EMQX татгалзав: {rc}")

    #   on_disconnect(client, userdata, disconnect_flags, reason_code, properties)
    def _on_disconnect(self, c, u, f, rc, p=None):
        self.connected = False

    def _on_message(self, c, u, msg):
        parts = msg.topic.split("/")
        if len(parts) < 7:
            return
        dev = parts[4]
        kind = parts[6]
        try:
            data = json.loads(msg.payload.decode())
        except (ValueError, UnicodeDecodeError):
            return
        if kind == "state":
            self._record_state(dev, data)
        elif kind == "request":
            self._send_chunk(dev, data)

    def _record_state(self, dev: str, data: dict) -> None:
        st = data.get("state", "?")
        with _lock, db() as c:
            c.execute("""UPDATE rollout_targets SET state=?, detail=?, updated_at=?
                         WHERE device_id=? AND rollout_id=(
                           SELECT id FROM rollouts WHERE state='running'
                           ORDER BY created_at DESC LIMIT 1)""",
                      (st, json.dumps(data)[:400], int(time.time()), dev))
            if st == "UPDATED" and data.get("version"):
                c.execute("UPDATE devices SET fw_version=?, last_seen=? WHERE id=?",
                          (data["version"], int(time.time()), dev))
        print(f"[ota] {dev}: {st} {data.get('progress', '')}")

    def _send_chunk(self, dev: str, data: dict) -> None:
        """Төхөөрөмж хэсэг гуйхад дискнээс уншиж илгээнэ."""
        fw_id, idx = data.get("fw_id"), int(data.get("chunk", 0))
        with db() as c:
            row = c.execute("SELECT * FROM firmware WHERE id=?", (fw_id,)).fetchone()
        if row is None:
            return
        with open(row["path"], "rb") as f:
            f.seek(idx * CHUNK)
            blob = f.read(CHUNK)
        topic = f"cnc302/{SITE}/{AREA}/{LINE}/{dev}/ota/chunk/{idx}"
        self.c.publish(topic, blob, qos=1)

    def offer(self, dev: str, fw: sqlite3.Row) -> None:
        topic = f"cnc302/{SITE}/{AREA}/{LINE}/{dev}/ota/offer"
        self.c.publish(topic, json.dumps({
            "fw_id": fw["id"], "version": fw["version"], "size": fw["size"],
            "sha256": fw["sha256"], "chunk_size": CHUNK,
            "chunks": (fw["size"] + CHUNK - 1) // CHUNK,
        }), qos=1)


bus = Bus()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    bus.start()
    yield
    bus.c.loop_stop()


app = FastAPI(title="CNC302 Device Registry", version="1.0", lifespan=lifespan)


# ─────────────────────────── Загварууд ───────────────────────────
class BulkReq(BaseModel):
    prefix: str = "dev"
    count: int = Field(10, ge=1, le=2000)
    label: str = "cnc302"


class ClaimReq(BaseModel):
    device_id: str
    secret: str = ""          # JIT-д ашиглах хуваалцсан нууц


class RolloutReq(BaseModel):
    fw_id: str
    canary_percent: int = Field(20, ge=1, le=100)
    devices: list[str] | None = None


# ─────────────────────────── Эндпойнтууд ───────────────────────────
@app.get("/health")
def health():
    with db() as c:
        n = c.execute("SELECT COUNT(*) n FROM devices").fetchone()["n"]
    return {"ok": True, "devices": n, "mqtt": bus.connected}


@app.post("/devices")
def bulk(req: BulkReq):
    """БӨӨНӨӨР бүртгэх: үйлдвэрт мэдэгдэж буй бүх төхөөрөмжийг урьдчилан."""
    out = []
    now = int(time.time())
    with _lock, db() as c:
        for i in range(1, req.count + 1):
            did = f"{req.prefix}{i:04d}"
            pw = secrets.token_urlsafe(12)
            try:
                c.execute("INSERT INTO devices(id,label,username,password,"
                          "created_at) VALUES(?,?,?,?,?)",
                          (did, req.label, did, pw, now))
            except sqlite3.IntegrityError:
                out.append({"id": did, "emqx": "already exists"})
                continue
            out.append({"id": did, "password": pw, "emqx": emqx_add_user(did, pw)})
    return {"mode": "bulk", "created": len(out), "devices": out}


@app.post("/devices/claim")
def claim(req: ClaimReq):
    """
    JIT (just-in-time): төхөөрөмж анх залгагдахдаа өөрөө бүртгүүлнэ.
    Бодит системд энд аюулгүй байдлын шалгалт (үйлдвэрийн сертификат,
    нэг удаагийн токен) байх ёстой — Лаб 2-ын хяналтын асуултад авч үзнэ.
    """
    now = int(time.time())
    pw = secrets.token_urlsafe(12)
    with _lock, db() as c:
        row = c.execute("SELECT * FROM devices WHERE id=?",
                        (req.device_id,)).fetchone()
        if row and row["state"] == "revoked":
            raise HTTPException(403, "төхөөрөмж хүчингүй болсон")
        if row:
            return {"mode": "jit", "id": row["id"], "password": row["password"],
                    "note": "аль хэдийн бүртгэлтэй"}
        c.execute("INSERT INTO devices(id,label,username,password,state,"
                  "created_at,last_seen) VALUES(?,?,?,?,?,?,?)",
                  (req.device_id, "jit", req.device_id, pw, "active", now, now))
    return {"mode": "jit", "id": req.device_id, "password": pw,
            "emqx": emqx_add_user(req.device_id, pw)}


@app.get("/devices")
def list_devices(state: str | None = None, limit: int = 500):
    q = "SELECT id,label,state,fw_version,created_at,last_seen FROM devices"
    a: tuple = ()
    if state:
        q += " WHERE state=?"; a = (state,)
    q += " ORDER BY id LIMIT ?"; a += (limit,)
    with db() as c:
        return {"devices": [dict(r) for r in c.execute(q, a)]}


@app.delete("/devices/{device_id}")
def revoke(device_id: str):
    """
    Хүчингүй болгох, ДАРААЛАЛ чухал:
      1) бүртгэлд тэмдэглэнэ,
      2) EMQX-ээс нэвтрэлтийг устгана → шинэ холболт татгалзагдана,
      3) идэвхтэй session-ыг хөөнө → дахин холбогдох гэхэд (2)-т бүдэрнэ.
    (3)-ыг (2)-оос өмнө хийвэл төхөөрөмж тэр дороо дахин холбогдож амжина.
    """
    with _lock, db() as c:
        r = c.execute("UPDATE devices SET state='revoked' WHERE id=?",
                      (device_id,))
        if r.rowcount == 0:
            raise HTTPException(404, "олдсонгүй")
    user = emqx_del_user(device_id)
    kicked = emqx_kick(device_id)
    return {"id": device_id, "state": "revoked", "emqx": user, "kicked": kicked}


@app.post("/firmware")
async def upload_fw(version: str, file: UploadFile = File(...)):
    blob = await file.read()
    sha = hashlib.sha256(blob).hexdigest()
    fw_id = sha[:12]
    path = FW_DIR / f"{fw_id}.bin"
    path.write_bytes(blob)
    with _lock, db() as c:
        c.execute("INSERT OR REPLACE INTO firmware(id,version,size,sha256,path,"
                  "created_at) VALUES(?,?,?,?,?,?)",
                  (fw_id, version, len(blob), sha, str(path), int(time.time())))
    return {"fw_id": fw_id, "version": version, "size": len(blob), "sha256": sha,
            "chunks": (len(blob) + CHUNK - 1) // CHUNK}


@app.get("/firmware")
def list_fw():
    with db() as c:
        return {"firmware": [dict(r) for r in
                             c.execute("SELECT id,version,size,sha256,created_at "
                                       "FROM firmware ORDER BY created_at DESC")]}


@app.post("/rollout")
def rollout(req: RolloutReq):
    """
    CANARY тараалт: эхлээд цөөн төхөөрөмжид, амжилттай бол бусдад.
    Энэ нь үйлдвэрлэлийн гол зарчим — 5000 төхөөрөмжийг нэг дор
    шинэчилж эвдэрвэл буцаах арга байхгүй.
    """
    with db() as c:
        fw = c.execute("SELECT * FROM firmware WHERE id=?", (req.fw_id,)).fetchone()
        if fw is None:
            raise HTTPException(404, "firmware олдсонгүй")
        if req.devices:
            targets = req.devices
        else:
            targets = [r["id"] for r in c.execute(
                "SELECT id FROM devices WHERE state!='revoked' ORDER BY id")]
    if not targets:
        raise HTTPException(400, "нэг ч төхөөрөмж алга")

    rid = secrets.token_hex(4)
    n_canary = max(1, len(targets) * req.canary_percent // 100)
    now = int(time.time())
    with _lock, db() as c:
        c.execute("INSERT INTO rollouts VALUES(?,?,?,?,?)",
                  (rid, req.fw_id, req.canary_percent, now, "running"))
        for i, d in enumerate(targets):
            c.execute("INSERT INTO rollout_targets VALUES(?,?,?,?,?,?)",
                      (rid, d, 0 if i < n_canary else 1, "pending", "", now))

    with db() as c:
        for d in targets[:n_canary]:
            bus.offer(d, fw)
    return {"rollout_id": rid, "targets": len(targets), "canary": n_canary,
            "note": "canary давалгаа илгээгдлээ. /rollout/{id}/promote-ээр үргэлжлүүлнэ."}


@app.post("/rollout/{rid}/promote")
def promote(rid: str):
    """Canary амжилттай бол үлдсэн бүх төхөөрөмжид тараана."""
    with db() as c:
        ro = c.execute("SELECT * FROM rollouts WHERE id=?", (rid,)).fetchone()
        if ro is None:
            raise HTTPException(404, "rollout олдсонгүй")
        if ro["state"] != "running":
            raise HTTPException(409, f"rollout төлөв: {ro['state']}")
        fw = c.execute("SELECT * FROM firmware WHERE id=?", (ro["fw_id"],)).fetchone()
        canary = list(c.execute(
            "SELECT state FROM rollout_targets WHERE rollout_id=? AND wave=0", (rid,)))
        failed = [r for r in canary if r["state"] in ("FAILED", "ROLLED_BACK")]
        if failed:
            with _lock:
                c.execute("UPDATE rollouts SET state='halted' WHERE id=?", (rid,))
                c.commit()        # HTTPException нь `with db()`-г rollback хийлгэнэ
            raise HTTPException(409,
                                f"canary-д {len(failed)} алдаа — тараалтыг зогсоов")
        unfinished = [r for r in canary if r["state"] != "UPDATED"]
        if unfinished:
            raise HTTPException(409, f"canary дуусаагүй: {len(unfinished)} төхөөрөмж "
                                     "UPDATED болоогүй — хүлээгээд дахин оролд")
        rest = [r["device_id"] for r in c.execute(
            "SELECT device_id FROM rollout_targets WHERE rollout_id=? AND wave=1",
            (rid,))]
    for d in rest:
        bus.offer(d, fw)
    return {"rollout_id": rid, "promoted": len(rest)}


@app.post("/rollout/{rid}/halt")
def halt(rid: str):
    with _lock, db() as c:
        c.execute("UPDATE rollouts SET state='halted' WHERE id=?", (rid,))
    return {"rollout_id": rid, "state": "halted"}


@app.get("/rollout/{rid}")
def rollout_status(rid: str):
    with db() as c:
        ro = c.execute("SELECT * FROM rollouts WHERE id=?", (rid,)).fetchone()
        if ro is None:
            raise HTTPException(404, "олдсонгүй")
        rows = [dict(r) for r in c.execute(
            "SELECT device_id,wave,state,updated_at FROM rollout_targets "
            "WHERE rollout_id=? ORDER BY wave,device_id", (rid,))]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    done = counts.get("UPDATED", 0)
    return JSONResponse({
        "rollout": dict(ro), "summary": counts,
        "success_rate": round(100 * done / len(rows), 1) if rows else 0.0,
        "targets": rows,
    })
