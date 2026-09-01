#!/usr/bin/env python3
"""
CNC302 Лаб 8 — Дижитал ихрийн загварчлал ба төлөв синхрончлол

Дижитал ихэр = бодит хөрөнгийн (asset) програм хангамжийн тусгал. Гурван
давхаргаас бүрдэнэ:

  1. БҮТЭЦ   — хөрөнгийн шатлал (кампус → барилга → өрөө → төхөөрөмж)
  2. ТӨЛӨВ   — одоогийн утга (сүүлийн хэмжилт, ажиллагааны төлөв)
  3. ЗАН ТӨЛӨВ — дүрэм, симуляц (жишээ: "20 минутын дараа хэм ямар байх вэ")

ThingsBoard-д: Asset + Relation + Attributes + Telemetry = ихэр.

  python3 twin_sync.py build      # хөрөнгийн шатлал үүсгэх
  python3 twin_sync.py sync       # төлөвийг тасралтгүй шинэчлэх
  python3 twin_sync.py show       # ихрийн одоогийн төлөвийг харах
  python3 twin_sync.py simulate --minutes 20
"""
from __future__ import annotations
import argparse, json, statistics, sys, time
import requests

TIMEOUT = 20


class TB:
    def __init__(self, url, user, pw):
        self.url = url.rstrip("/")
        self.s = requests.Session()
        r = self.s.post(f"{self.url}/api/auth/login",
                        json={"username": user, "password": pw}, timeout=TIMEOUT)
        r.raise_for_status()
        self.s.headers["X-Authorization"] = f"Bearer {r.json()['token']}"

    def asset(self, name, atype):
        r = self.s.post(f"{self.url}/api/asset",
                        json={"name": name, "type": atype}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()

    def find_asset(self, name):
        r = self.s.get(f"{self.url}/api/tenant/assets", params={"assetName": name},
                       timeout=TIMEOUT)
        return r.json() if r.status_code == 200 else None

    def find_device(self, name):
        r = self.s.get(f"{self.url}/api/tenant/devices", params={"deviceName": name},
                       timeout=TIMEOUT)
        return r.json() if r.status_code == 200 else None

    def relate(self, from_id, from_type, to_id, to_type, rel="Contains"):
        body = {"from": {"id": from_id, "entityType": from_type},
                "to": {"id": to_id, "entityType": to_type},
                "type": rel, "typeGroup": "COMMON"}
        self.s.post(f"{self.url}/api/relation", json=body, timeout=TIMEOUT)

    def attrs(self, eid, etype, scope, data):
        self.s.post(f"{self.url}/api/plugins/telemetry/{etype}/{eid}/{scope}",
                    json=data, timeout=TIMEOUT)

    def telemetry(self, eid, etype, data):
        self.s.post(f"{self.url}/api/plugins/telemetry/{etype}/{eid}/timeseries/ANY",
                    json=data, timeout=TIMEOUT)

    def latest(self, eid, etype, keys):
        r = self.s.get(
            f"{self.url}/api/plugins/telemetry/{etype}/{eid}/values/timeseries",
            params={"keys": ",".join(keys)}, timeout=TIMEOUT)
        return r.json() if r.status_code == 200 else {}

    def relations(self, eid, etype):
        r = self.s.get(f"{self.url}/api/relations/info",
                       params={"fromId": eid, "fromType": etype}, timeout=TIMEOUT)
        return r.json() if r.status_code == 200 else []


def influx(base, db, q):
    r = requests.post(f"{base.rstrip('/')}/api/v3/query_sql",
                      json={"db": db, "q": q, "format": "json"}, timeout=60)
    r.raise_for_status()
    return r.json()


# ───────────────────────── build ─────────────────────────

HIERARCHY = {
    "campus-must": ("campus", {
        "building-a": ("building", {
            "room-a301": ("room", ["dev0000", "dev0001"]),
            "room-a302": ("room", ["dev0002"]),
        }),
        "building-b": ("building", {
            "room-b101": ("room", ["dev0003"]),
        }),
    }),
}


def cmd_build(tb: TB, a) -> int:
    created = {}

    def make(name, atype, props=None):
        ex = tb.find_asset(name)
        if ex:
            print(f"  = {atype:<9} {name} (аль хэдийн байна)")
            node = ex
        else:
            node = tb.asset(name, atype)
            print(f"  + {atype:<9} {name}")
        created[name] = node
        if props:
            tb.attrs(node["id"]["id"], "ASSET", "SERVER_SCOPE", props)
        return node

    def walk(tree, parent=None):
        for name, (atype, child) in tree.items():
            node = make(name, atype, {"twin_version": "1.0",
                                      "created_at": int(time.time() * 1000)})
            if parent:
                tb.relate(parent["id"]["id"], "ASSET", node["id"]["id"], "ASSET")
            if isinstance(child, dict):
                walk(child, node)
            else:
                for dev in child:
                    d = tb.find_device(dev)
                    if not d:
                        print(f"    ! төхөөрөмж {dev} олдсонгүй — Лаб 2-ыг ажиллуул")
                        continue
                    tb.relate(node["id"]["id"], "ASSET", d["id"]["id"], "DEVICE")
                    print(f"    → {dev} холбогдлоо")

    print("→ Хөрөнгийн шатлал үүсгэж байна…")
    walk(HIERARCHY)
    print(f"\n✓ {len(created)} хөрөнгө бэлэн. ThingsBoard → Entities → Assets")
    return 0


# ───────────────────────── sync ─────────────────────────

def cmd_sync(tb: TB, a) -> int:
    """Доод давхаргын төхөөрөмжийн утгыг нэгтгэж дээд хөрөнгийн төлөвийг шинэчилнэ."""
    print(f"→ {a.interval:.0f} сек тутам ихрийн төлөвийг шинэчилж байна "
          f"(Ctrl+C зогсооно)…")
    rooms = {"room-a301": ["dev0000", "dev0001"],
             "room-a302": ["dev0002"], "room-b101": ["dev0003"]}
    try:
        while True:
            for room, devs in rooms.items():
                asset = tb.find_asset(room)
                if not asset:
                    continue
                vals = []
                for d in devs:
                    rows = influx(a.influx, a.db,
                                  f"SELECT temperature, vibration_rms FROM telemetry "
                                  f"WHERE device = '{d}' "
                                  f"AND time > now() - INTERVAL '5 minutes' "
                                  f"ORDER BY time DESC LIMIT 20")
                    vals.extend(rows)
                if not vals:
                    continue
                temps = [v["temperature"] for v in vals if v.get("temperature")]
                vibs = [v["vibration_rms"] for v in vals if v.get("vibration_rms")]
                state = {
                    "avg_temperature": round(statistics.fmean(temps), 2) if temps else None,
                    "max_vibration": round(max(vibs), 3) if vibs else None,
                    "device_count": len(devs),
                    "samples": len(vals),
                    "health": ("ok" if (vibs and max(vibs) < 1.5) else "warning"),
                    "updated_at": int(time.time() * 1000),
                }
                tb.telemetry(asset["id"]["id"], "ASSET",
                             {k: v for k, v in state.items() if v is not None})
                print(f"  {room:<12} хэм={state['avg_temperature']} "
                      f"чичиргээ={state['max_vibration']} "
                      f"төлөв={state['health']}")
            time.sleep(a.interval)
    except KeyboardInterrupt:
        print("\nЗогслоо.")
    return 0


# ───────────────────────── show / simulate ─────────────────────────

def cmd_show(tb: TB, a) -> int:
    keys = ["avg_temperature", "max_vibration", "health", "samples"]
    print(f"\n{'ХӨРӨНГӨ':<14}{'ХЭМ':>8}{'ЧИЧИРГЭЭ':>11}{'ТӨЛӨВ':>11}{'ДЭЭЖ':>7}")
    print("-" * 51)
    for room in ("room-a301", "room-a302", "room-b101"):
        asset = tb.find_asset(room)
        if not asset:
            print(f"{room:<14}{'үүсээгүй':>37}")
            continue
        t = tb.latest(asset["id"]["id"], "ASSET", keys)
        g = lambda k: (t.get(k) or [{}])[0].get("value", "—")
        print(f"{room:<14}{str(g('avg_temperature')):>8}"
              f"{str(g('max_vibration')):>11}{str(g('health')):>11}"
              f"{str(g('samples')):>7}")
    return 0


def cmd_simulate(tb: TB, a) -> int:
    """
    Ихрийн ГУРАВ ДАХЬ давхарга: зан төлөв. Шугаман экстраполяциар
    N минутын дараах хэмийг таамаглана.
    """
    for room, dev in (("room-a301", "dev0000"), ("room-a302", "dev0002")):
        rows = influx(a.influx, a.db,
                      f"SELECT time, temperature FROM telemetry "
                      f"WHERE device = '{dev}' "
                      f"AND time > now() - INTERVAL '30 minutes' "
                      f"ORDER BY time ASC LIMIT 200")
        temps = [r["temperature"] for r in rows if r.get("temperature")]
        if len(temps) < 10:
            print(f"{room}: өгөгдөл хангалтгүй ({len(temps)} дээж)")
            continue
        n = len(temps)
        xs = list(range(n))
        mx, my = statistics.fmean(xs), statistics.fmean(temps)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, temps))
        den = sum((x - mx) ** 2 for x in xs) or 1
        slope = num / den
        step_min = 30 / n
        pred = temps[-1] + slope * (a.minutes / step_min)
        print(f"{room}: одоо {temps[-1]:.2f}°C, "
              f"{a.minutes} мин дараа {pred:.2f}°C "
              f"(хандлага {slope/step_min:+.3f} °C/мин)")
        if pred > 35:
            print(f"  ⚠ {a.minutes} минутын дараа 35°C давна — урьдчилсан дохиолол")
    print("\nЭнэ бол хамгийн энгийн зан төлөвийн загвар. Бодит ихэрт "
          "физик загвар эсвэл ML ашиглана (Лаб 6-ийн загвар энд орж болно).")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Дижитал ихрийн синхрончлол")
    p.add_argument("cmd", choices=["build", "sync", "show", "simulate"])
    p.add_argument("--url", default="http://localhost:8080")
    p.add_argument("--user", default="tenant@thingsboard.org")
    p.add_argument("--password", default="tenant")
    p.add_argument("--influx", default="http://localhost:8181")
    p.add_argument("--db", default="cnc302")
    p.add_argument("--interval", type=float, default=15)
    p.add_argument("--minutes", type=float, default=20)
    a = p.parse_args()
    tb = TB(a.url, a.user, a.password)
    return {"build": cmd_build, "sync": cmd_sync,
            "show": cmd_show, "simulate": cmd_simulate}[a.cmd](tb, a)


if __name__ == "__main__":
    sys.exit(main())
