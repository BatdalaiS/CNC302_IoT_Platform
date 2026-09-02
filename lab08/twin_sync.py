#!/usr/bin/env python3
"""
CNC302 Лаб 8 — Дижитал ихрийн загварчлал ба төлөв синхрончлол

Дижитал ихэр = бодит хөрөнгийн (asset) програм хангамжийн тусгал. Гурван
давхаргаас бүрдэнэ:

  1. БҮТЭЦ   — хөрөнгийн шатлал (site → area → line → device)
  2. ТӨЛӨВ   — одоогийн утга (сүүлийн хэмжилт, ажиллагааны төлөв)
  3. ЗАН ТӨЛӨВ — дүрэм, симуляц (жишээ: "20 минутын дараа хэм ямар байх вэ")

ЭНЭ ЛАБОРАТОРИД ThingsBoard БАЙХГҮЙ. Гурван давхаргыг бид өөрсдөө хөтөлнө:

  БҮТЭЦ  → UNS шатлал (Лаб 3) + `registry` (:8090) дэх төхөөрөмжийн бүртгэл
           → lab08/out/twin.json файлд хадгална
  ТӨЛӨВ  → (а) ТҮҮХ: InfluxDB 3 (:8181, зөөврийн компьютер)
           (б) АМЬД: ирмэгээс ГҮҮРЭЭР ирсэн MQTT мессеж — үүлний EMQX
               (:1883) дээрх `status`, `bridge/state`, `telemetry`
  ЗАН ТӨЛӨВ → `simulate` (шугаман экстраполяци, оюутан сайжруулна)

Топологи:
  Raspberry Pi 3B (ирмэг)  : mosquitto + edge_agent  → гүүр → үүл
  Зөөврийн компьютер (үүл) : EMQX, InfluxDB, registry, Grafana, Ollama
  Энэ скрипт нь ҮҮЛНИЙ талд ажиллана.

  python3 twin_sync.py build      # шатлалыг үүсгэж бүртгэлтэй тулгах
  python3 twin_sync.py sync       # төлөвийг тасралтгүй шинэчлэх
  python3 twin_sync.py show       # ихрийн одоогийн төлөвийг харах
  python3 twin_sync.py simulate --minutes 20
"""
from __future__ import annotations
import argparse, json, os, statistics, sys, time
import requests

TIMEOUT = 20
TWIN_FILE_DEFAULT = "lab08/out/twin.json"


# ───────────────────── эх сурвалжууд (үүлний тал) ─────────────────────

def registry_get(base: str, path: str, **params) -> dict:
    """Лаб 2-ын бүртгэл. ThingsBoard-ын REST API-г ЭНЭ орлоно."""
    r = requests.get(f"{base.rstrip('/')}{path}", params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def influx(base: str, db: str, q: str) -> list[dict]:
    r = requests.post(f"{base.rstrip('/')}/api/v3/query_sql",
                      json={"db": db, "q": q, "format": "json"}, timeout=60)
    r.raise_for_status()
    return r.json()


def influx_write(base: str, db: str, lines: list[str]) -> int:
    """
    Ихрийн төлөвийг ЦАГ ЦУВАА болгон буцааж бичнэ (measurement: twin_state).
    ThingsBoard-ын ASSET telemetry-г яг энэ орлоно — Grafana-д ижилхэн
    харагдана, гэхдээ ямар ч платформын хараат байдалгүй.
    """
    r = requests.post(f"{base.rstrip('/')}/api/v3/write_lp",
                      params={"db": db, "precision": "millisecond"},
                      data="\n".join(lines).encode(), timeout=30)
    if r.status_code not in (200, 204):
        raise RuntimeError(f"InfluxDB бичилт амжилтгүй {r.status_code}: "
                           f"{r.text[:200]}")
    return len(lines)


def live_state(host: str, port: int, site: str, area: str, line: str,
               seconds: float = 3.0) -> dict:
    """
    АМЬД төлөв: үүлний брокероос retained мессежийг цуглуулна.

    Pi 3B-гийн mosquitto нь эдгээрийг ГҮҮРЭЭР (bridge) үүл рүү дамжуулдаг
    тул үүлэн дээр сууж байгаад ирмэгийн бодит төлөвийг харна. Гүүр
    тасарсан бол `bridge/state` = 0 болж, retained `status` хуучирна —
    ихэр "хуучирсан төлөв"-ийг ЗААВАЛ ялгаж харуулах ёстой.
    """
    try:
        import paho.mqtt.client as mqtt
        from paho.mqtt.enums import CallbackAPIVersion
    except ImportError:
        print("  ! paho-mqtt суулгаагүй — амьд төлөвгүйгээр үргэлжилнэ",
              file=sys.stderr)
        return {}

    out: dict[str, dict] = {}

    def on_message(cl, u, m):
        parts = m.topic.split("/")
        if len(parts) < 6:
            return
        dev = parts[4]
        chan = "/".join(parts[5:])
        try:
            payload = json.loads(m.payload.decode())
        except (ValueError, UnicodeDecodeError):
            payload = {"raw": m.payload.decode(errors="replace")[:60]}
        out.setdefault(dev, {})[chan] = payload

    c = mqtt.Client(CallbackAPIVersion.VERSION2,
                    client_id=f"twin-{os.getpid()}", protocol=mqtt.MQTTv5)
    c.on_message = on_message
    try:
        c.connect(host, port, 30)
    except OSError as e:
        print(f"  ! MQTT ({host}:{port}) холбогдсонгүй: {e}", file=sys.stderr)
        return {}
    base = f"cnc302/{site}/{area}/{line}"
    for chan in ("status", "health", "telemetry", "bridge/state"):
        c.subscribe(f"{base}/+/{chan}", qos=1)
    c.loop_start()
    time.sleep(seconds)
    c.loop_stop(); c.disconnect()
    return out


# ───────────────────────── build (БҮТЭЦ) ─────────────────────────

def cmd_build(a) -> int:
    """
    Шатлалыг UNS-ээс үүсгэнэ. Хөрөнгийн мод нь MQTT сэдвийн модтой ЯГ
    ижил байх ёстой — эс тэгвээс хоёр үнэн зэрэг оршиж, аль нь зөв нь
    хэн ч мэдэхгүй болно (Лаб 3-ын гол сургамж).
    """
    devices: list[dict] = []
    try:
        data = registry_get(a.registry, "/devices", limit=500)
        devices = data.get("devices", [])
        print(f"→ бүртгэлээс {len(devices)} төхөөрөмж уншлаа ({a.registry})")
    except requests.RequestException as e:
        print(f"! бүртгэлд хандаж чадсангүй: {e}")
        print("  registry ажиллаж байна уу? "
              "(stack: docker compose --profile core up -d registry)")

    extra = [d for d in (a.devices or "").split(",") if d.strip()]
    ids = [d["id"] for d in devices if d.get("state") != "revoked"] + extra
    if not ids:
        print("! нэг ч төхөөрөмж алга. Лаб 2-ыг ажиллуулах эсвэл "
              "--devices pi3b-01,dev0001 гэж заана.")
        return 1

    twin = {
        "version": "2.0",
        "created_at": int(time.time() * 1000),
        "uns": {"site": a.site, "area": a.area, "line": a.line},
        "nodes": {
            a.site: {"type": "site", "children": [a.area]},
            f"{a.site}/{a.area}": {"type": "area", "children": [a.line]},
            f"{a.site}/{a.area}/{a.line}": {"type": "line", "devices": ids},
        },
        "devices": {d["id"]: {"state": d.get("state"),
                              "fw_version": d.get("fw_version"),
                              "label": d.get("label")}
                    for d in devices},
    }
    os.makedirs(os.path.dirname(a.twin_file) or ".", exist_ok=True)
    with open(a.twin_file, "w", encoding="utf-8") as f:
        json.dump(twin, f, ensure_ascii=False, indent=2)

    print(f"  + site     {a.site}")
    print(f"  + area     {a.site}/{a.area}")
    print(f"  + line     {a.site}/{a.area}/{a.line}")
    for d in ids:
        st = twin["devices"].get(d, {}).get("state", "бүртгэлгүй")
        print(f"    → {d:<12} ({st})")
    print(f"\n✓ ихрийн бүтэц: {a.twin_file}")
    print("  UNS сэдэв ба хөрөнгийн шатлал ижил байгааг шалга:")
    print(f"    mosquitto_sub -h {a.mqtt_host} "
          f"-t 'cnc302/{a.site}/{a.area}/{a.line}/#' -v")
    return 0


def load_twin(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        print(f"! {path} олдсонгүй — эхлээд `twin_sync.py build` ажиллуул",
              file=sys.stderr)
        return {}


# ───────────────────────── sync (ТӨЛӨВ) ─────────────────────────

def esc(s) -> str:
    return str(s).replace(" ", r"\ ").replace(",", r"\,").replace("=", r"\=")


def cmd_sync(a) -> int:
    """Төхөөрөмжийн утгыг нэгтгэж ШУГАМЫН (line) төлөвийг шинэчилнэ."""
    twin = load_twin(a.twin_file)
    if not twin:
        return 1
    node = f"{a.site}/{a.area}/{a.line}"
    devs = twin["nodes"].get(node, {}).get("devices", [])
    print(f"→ {a.interval:.0f} сек тутам '{node}' ихрийн төлөвийг "
          f"шинэчилж байна (Ctrl+C зогсооно)…")
    print(f"  түүх: {a.influx}   амьд: mqtt://{a.mqtt_host}:{a.mqtt_port}")
    try:
        while True:
            live = live_state(a.mqtt_host, a.mqtt_port, a.site, a.area,
                              a.line, seconds=min(3.0, a.interval / 3))
            online = sum(1 for d in devs
                         if live.get(d, {}).get("status", {}).get("online"))
            rows: list[dict] = []
            for d in devs:
                try:
                    rows.extend(influx(
                        a.influx, a.db,
                        f"SELECT {a.temp_field}, {a.vib_field} FROM telemetry "
                        f"WHERE device = '{d}' "
                        f"AND time > now() - INTERVAL '5 minutes' "
                        f"ORDER BY time DESC LIMIT 20"))
                except requests.RequestException as e:
                    print(f"  ! InfluxDB: {e}")
                    break
            temps = [r[a.temp_field] for r in rows if r.get(a.temp_field) is not None]
            vibs = [r[a.vib_field] for r in rows if r.get(a.vib_field) is not None]

            # Ихрийн эрүүл мэнд: зөвхөн хэмжилтээр биш, ХОЛБОО-гоор ч
            # тодорхойлогдоно. Өгөгдөл ирэхгүй байгаа ихэр бол "ok" биш.
            if not rows:
                health = "stale"
            elif vibs and max(vibs) >= a.vib_warn:
                health = "warning"
            elif online < len(devs):
                health = "degraded"
            else:
                health = "ok"

            state = {
                "avg_temperature": round(statistics.fmean(temps), 2) if temps else None,
                "max_vibration": round(max(vibs), 3) if vibs else None,
                "device_count": len(devs),
                "devices_online": online,
                "samples": len(rows),
                "health": health,
            }
            tags = (f"site={esc(a.site)},area={esc(a.area)},line={esc(a.line)},"
                    f"node={esc(node)}")
            fields = [f"{k}={v}" for k, v in state.items()
                      if v is not None and not isinstance(v, str)]
            fields.append(f'health="{state["health"]}"')
            lp = f"twin_state,{tags} {','.join(fields)} {int(time.time()*1000)}"
            try:
                influx_write(a.influx, a.db, [lp])
            except (requests.RequestException, RuntimeError) as e:
                print(f"  ! ихрийн төлөв бичигдсэнгүй: {e}")
            print(f"  {node:<22} хэм={state['avg_temperature']} "
                  f"чичиргээ={state['max_vibration']} "
                  f"онлайн={online}/{len(devs)} төлөв={health}")
            time.sleep(a.interval)
    except KeyboardInterrupt:
        print("\nЗогслоо.")
    return 0


# ───────────────────────── show / simulate ─────────────────────────

def cmd_show(a) -> int:
    twin = load_twin(a.twin_file)
    if not twin:
        return 1
    node = f"{a.site}/{a.area}/{a.line}"
    devs = twin["nodes"].get(node, {}).get("devices", [])

    print(f"\nИХЭР: {node}   ({len(devs)} төхөөрөмж)")
    print(f"{'ХӨРӨНГӨ':<24}{'ХЭМ':>8}{'ЧИЧИРГЭЭ':>11}{'ОНЛАЙН':>9}"
          f"{'ТӨЛӨВ':>10}{'ДЭЭЖ':>7}")
    print("-" * 69)
    try:
        rows = influx(a.influx, a.db,
                      "SELECT time, node, avg_temperature, max_vibration, "
                      "devices_online, device_count, health, samples "
                      "FROM twin_state ORDER BY time DESC LIMIT 20")
    except requests.RequestException as e:
        print(f"! InfluxDB: {e}")
        return 2
    seen: set[str] = set()
    for r in rows:
        n = str(r.get("node"))
        if n in seen:
            continue
        seen.add(n)
        print(f"{n:<24}{str(r.get('avg_temperature','—')):>8}"
              f"{str(r.get('max_vibration','—')):>11}"
              f"{str(r.get('devices_online','—'))+'/'+str(r.get('device_count','—')):>9}"
              f"{str(r.get('health','—')):>10}{str(r.get('samples','—')):>7}")
    if not seen:
        print("(twin_state хоосон — эхлээд `sync` ажиллуул)")

    # Амьд төлөв: гүүр ажиллаж байгаа эсэх нь ихрийн НАЙДВАРТАЙ БАЙДЛЫН хэмжүүр
    live = live_state(a.mqtt_host, a.mqtt_port, a.site, a.area, a.line)
    if live:
        print("\nАМЬД ТӨЛӨВ (үүлний брокероос, гүүрээр ирсэн):")
        for dev, chans in sorted(live.items()):
            st = chans.get("status", {})
            tel = chans.get("telemetry", {})
            print(f"  {dev:<14} online={st.get('online')} "
                  f"seq={tel.get('seq','—')} "
                  f"score={tel.get('score','—')} "
                  f"infer_ms={tel.get('infer_ms','—')}")
    else:
        print("\n(амьд мессеж ирсэнгүй — гүүр эсвэл агент зогссон байж болно)")
    return 0


def cmd_simulate(a) -> int:
    """
    Ихрийн ГУРАВ ДАХЬ давхарга: зан төлөв. Шугаман экстраполяциар
    N минутын дараах хэмийг таамаглана.
    """
    twin = load_twin(a.twin_file)
    if not twin:
        return 1
    node = f"{a.site}/{a.area}/{a.line}"
    devs = twin["nodes"].get(node, {}).get("devices", [])[:4]
    for dev in devs:
        try:
            rows = influx(a.influx, a.db,
                          f"SELECT time, {a.temp_field} FROM telemetry "
                          f"WHERE device = '{dev}' "
                          f"AND time > now() - INTERVAL '30 minutes' "
                          f"ORDER BY time ASC LIMIT 200")
        except requests.RequestException as e:
            print(f"! InfluxDB: {e}")
            return 2
        temps = [r[a.temp_field] for r in rows if r.get(a.temp_field) is not None]
        if len(temps) < 10:
            print(f"{dev}: өгөгдөл хангалтгүй ({len(temps)} дээж)")
            continue
        n = len(temps)
        xs = list(range(n))
        mx, my = statistics.fmean(xs), statistics.fmean(temps)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, temps))
        den = sum((x - mx) ** 2 for x in xs) or 1
        slope = num / den
        step_min = 30 / n
        pred = temps[-1] + slope * (a.minutes / step_min)
        print(f"{dev}: одоо {temps[-1]:.2f}°C, "
              f"{a.minutes} мин дараа {pred:.2f}°C "
              f"(хандлага {slope/step_min:+.3f} °C/мин)")
        if pred > a.temp_alarm:
            print(f"  ⚠ {a.minutes} минутын дараа {a.temp_alarm}°C давна "
                  f"— урьдчилсан дохиолол")
    print("\nЭнэ бол хамгийн энгийн зан төлөвийн загвар. Бодит ихэрт "
          "физик загвар эсвэл ML ашиглана (Лаб 6-ийн загвар энд орж болно).")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Дижитал ихрийн синхрончлол (registry + InfluxDB + MQTT)",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("cmd", choices=["build", "sync", "show", "simulate"])
    # ── үүлний давхарга (зөөврийн компьютер) ──
    p.add_argument("--registry", default=os.getenv("REGISTRY_URL",
                                                   "http://localhost:8090"))
    p.add_argument("--influx", default=os.getenv("INFLUX_URL",
                                                 "http://localhost:8181"))
    p.add_argument("--db", default=os.getenv("INFLUX_DB", "cnc302"))
    # Амьд төлөв нь ИРМЭГЭЭС гүүрээр ирдэг тул үүлний EMQX-ийг сонсоно.
    # Pi дээрээс шууд ажиллуулбал: --mqtt-host localhost (ирмэгийн mosquitto)
    p.add_argument("--mqtt-host", default=os.getenv("MQTT_HOST", "localhost"))
    p.add_argument("--mqtt-port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    # ── UNS байрлал ──
    p.add_argument("--site", default=os.getenv("SITE", "shutis"))
    p.add_argument("--area", default=os.getenv("AREA", "mhts"))
    p.add_argument("--line", default=os.getenv("LINE", "lab"))
    p.add_argument("--devices", help="бүртгэлээс гадуур нэмэх ID-ууд "
                                     "(таслалаар: pi3b-01,pi3b-02)")
    p.add_argument("--twin-file", default=TWIN_FILE_DEFAULT)
    # ── талбарын нэрс (Node-RED шугамын бичсэнээр) ──
    p.add_argument("--temp-field", default="temperature",
                   help="ирмэгийн агентын түүхий сувагт proc_temp_c")
    p.add_argument("--vib-field", default="vibration_rms",
                   help="ирмэгийн агентын түүхий сувагт vibration_g")
    p.add_argument("--vib-warn", type=float, default=1.5)
    p.add_argument("--temp-alarm", type=float, default=35.0)
    p.add_argument("--interval", type=float, default=15)
    p.add_argument("--minutes", type=float, default=20)
    a = p.parse_args()
    return {"build": cmd_build, "sync": cmd_sync,
            "show": cmd_show, "simulate": cmd_simulate}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
