# Лаб 5 — Өгөгдлийн шугам ба холбоос тасрах

| | |
|---|---|
| **7 хоног** | XI |
| **Хугацаа** | 4 цаг |
| **Суралцахуйн үр дүн** | ҮД4 (үнэлэх), ҮД6, ҮД7 |
| **Үнэлгээ** | Бичгийн тайлан, 10 оноо |
| **Гол хэмжилт** | Store-and-forward-ийн алдагдал, **RPO** ба **MTTR** секундээр |

---

## 1. Зорилго

Хоёр хагас. Эхний хагаст 💻 үүл дээр бүрэн өгөгдлийн шугам барина:

```
🥧 mosquitto ══гүүр══▶ 💻 EMQX ─▶ Node-RED ─▶ InfluxDB 3 ─▶ Grafana
                                   (задлах,     (хадгалах)    (харах)
                                    шалгах)  └─▶ dead-letter
```

Хоёр дахь хагас — **энэ бол лабораторийн зүрх** — өгсөх урсгалыг (uplink) тасалж, юу амьд үлдэхийг тоогоор хэмжинэ. Хоёр тоог гаргана:

- **RPO** (Recovery Point Objective) — хэдэн секундын өгөгдөл **бүрмөсөн алдагдав**
- **MTTR** (Mean Time To Recovery) — шугам бүрэн эдгэрэх хүртэл хэдэн секунд өнгөрөв

> **Курсын тодорхойлолт.** RPO нь угтаа "хэдий хэмжээний өгөгдлийн алдагдлыг (хугацаагаар) хүлээн зөвшөөрөх вэ" гэсэн **зорилт**; MTTR нь олон эвдрэлийн сэргэх хугацааны **дундаж**. Энэ лабораторид бид нэг туршилт бүрийн **бодит** утгыг хэмжинэ: RPO = бүрмөсөн алдагдсан хамгийн урт тасралтгүй хэсгийн үргэлжлэл (с); MTTR = өгсөх урсгал сэргэснээс хойш тасалдлын үеэр илгээсэн сүүлийн мессеж санд хүрэх хүртэлх хугацаа (с). Олон давталтын дундаж нь жинхэнэ MTTR болно.

Энэ хоёр өөр үзүүлэлт: систем 5 секундын дараа сэргэж болно (сайн MTTR), гэхдээ тэр хугацааны өгөгдөл бүрэн алдагдсан байж болно (муу RPO).

> **⚠ ЭНЭ ЛАБОРАТОРИЙН ХАМГИЙН ЧУХАЛ УРХИ.** Өгсөх урсгал сэргэхэд гүүр хуримтлагдсан мессежээ **нэг тэсрэлтээр** урсгана. Хэрэв та `mosquitto_sub`-ыг тэр тэсрэлтийн **дараа** асаавал юу ч харагдахгүй — MQTT нь өнгөрсөн мессежийг шинэ захиалагчид дахин илгээхгүй. Тэгээд "store-and-forward ажиллаагүй" гэсэн **буруу дүгнэлт** гарна. Дахин илгээлт болсон эсэхийг **зөвхөн InfluxDB дотор** (эсвэл эхнээс нь ажиллаж байсан тогтвортой session-тэй захиалагчаар) шалгана.

---

## 2. Урьдчилсан нөхцөл ба бэлтгэл (20 мин)

- Лаб 1–4 дууссан, `lab04-done` tag тавигдсан. Лаб 2-ын authenticator унтраалттай (`authn false`).

> 💡 **Алхмуудыг дарааллаар нь хий.** Алхам бүрийн төгсгөлд ✅ **Шалгах** хэсэг бий. Үр дүн нь таарахгүй бол **цааш бүү яв** — ❌ мөр эсвэл §8-аас шалтгааныг ол.

### 2.1 Терминалууд — **таван** цонх

| Цонх | Хаана | Үүрэг энэ лабд |
|---|---|---|
| **[🥧 Pi-1]** | Raspberry Pi (`ssh pi`) | гүүрийн төлөвийг `bridge.jsonl`-д бичнэ — **Алхам 3-аас лабын төгсгөл хүртэл бүү хаа** |
| **[🥧 Pi-2]** | Raspberry Pi (`ssh pi`) | `data_integrity.py publish` / `verify` |
| **[🥧 Pi-3]** | Raspberry Pi (`ssh pi`) | эвдрэл үүсгэх (`failure_inject.sh`), ажиглалт |
| **[💻 Ubuntu-1]** | Зөөврийн компьютер (WSL) | стек, InfluxDB, Node-RED |
| **[💻 Ubuntu-2]** | Зөөврийн компьютер (WSL) | симулятор, ажиглалт |

### 2.2 Орчноо бэлтгэх — **цонх нээх бүрт** ажиллуулна

**[💻 Ubuntu-1]** ба **[💻 Ubuntu-2]**
```bash
cd ~/cnc302 && source .venv/bin/activate
```

**[🥧 Pi-1]**, **[🥧 Pi-2]**, **[🥧 Pi-3]**
```bash
cd ~/cnc302
PY=~/cnc302/edge/.venv/bin/python
set -a && source ~/cnc302/edge/.env && set +a
echo "$CLOUD_HOST / $SITE"
```

✅ `192.168.1.100 / shutis`.

> ⚠️ `data_integrity.py` нь сэдвийг `cnc302/shutis/mhts/lab/integrity/telemetry` гэж **тогтмол** бичдэг. Таны `SITE` нь `shutis`-ээс өөр бол гүүр мессежийг дамжуулахгүй — багшид хандана.

### 2.3 Нэг удаагийн бэлтгэл

**[🥧 Pi-1]**
```bash
git pull
mkdir -p lab05/out
sudo apt install -y stress-ng iptables
$PY -m pip install "requests>=2.31,<3"
$PY -c "import requests, paho.mqtt; print('OK')"
```

✅ `OK`. (`requests`-ийг Лаб 4-т суулгасан бол `Requirement already satisfied`.)

- `failure_inject.sh` нь `iptables` (байхгүй бол `nft`)-ээр Pi → компьютер 1883 портыг хаана, `sudo` шаарддаг.
- `data_integrity.py verify` нь компьютер дээрх InfluxDB-г (`$CLOUD_HOST:8181`) шууд асуудаг — SETUP А.6-ийн галт ханын дүрэмд 8181 нээгдсэн.

**[💻 Ubuntu-1]**
```bash
git pull
mkdir -p lab05/out
```

### 2.4 `pipeline` профайлыг асаах

**[💻 Ubuntu-1]**
```bash
cd ~/cnc302/stack && make up-pipeline && make health
sleep 40; docker compose ps
cd ~/cnc302
```

✅ `make health` дөрвөн мөр `200`; `docker compose ps`-д `cnc302-nodered` → `Up (healthy)`. `starting` бол 30 сек хүлээгээд дахин `docker compose ps`.

### 2.5 Гүүр ба цаг

**[🥧 Pi-3]**
```bash
cd ~/cnc302/edge && make check && make up && make link
```

✅ `make check` бүгд `OK` (NTP мөр **заавал** OK), `bridge/state 1` → `Ctrl + C`, `cd ~/cnc302`.

> **Цагийн тохирол.** MTTR-ыг Pi-гийн цаг (тасалдлын цаг) ба зөөврийн компьютерийн цаг (`rx_ms`) хоёрыг харьцуулж тооцдог. Хоёр хост дээр `timedatectl` → `System clock synchronized: yes` байх ёстой (**[💻 Ubuntu-1]** дээр ч шалга).

---

## 3. Онолын сануулга

### Баталгаа нь давхаргуудын үржвэр биш, хамгийн сул холбоосоор тодорхойлогдоно

QoS 2-оор илгээсэн мессеж брокерт баттай хүрнэ. Гэвч брокероос Node-RED, тэндээс InfluxDB руу явах замд MQTT-ийн баталгаа **байхгүй**. Тиймээс "төгсгөл-төгсгөлийн найдвартай байдал" гэдэг нь давхарга бүрийн баталгааны нийлбэр биш — **хамгийн сул холбоос** юм.

### Хаана буферлэгдэх вэ

| Эвдрэл | Хэн буферлэдэг | Хязгаар |
|---|---|---|
| **Өгсөх урсгал тасарсан** | ирмэгийн mosquitto-гийн гүүрний дараалал (**RAM**, үе үе microSD руу хуулна) | `max_queued_messages` / `max_queued_bytes`, контейнерийн RAM (128 MiB) |
| Ирмэгийн брокер унтарсан | төхөөрөмж өөрөө (кодлогдсон бол) | төхөөрөмжийн RAM |
| Node-RED/InfluxDB унтарсан | Node-RED-ийн dead-letter файл | диск |
| Диск дүүрсэн | **хэн ч үгүй** | — |

### Store-and-forward-ийн гурван тохиргоо

`edge/mosquitto/mosquitto.conf` ба `conf.d/bridge.conf` дахь гурван мөр л энэ бүхнийг тодорхойлно:

| Тохиргоо | Хаана | Үүрэг |
|---|---|---|
| `cleansession false` | bridge.conf | тасрахад **алсын** (EMQX) талын захиалга, session хадгалагдана; `true` бол холбоос тасрахад алсын захиалга, мессеж цэвэрлэгдэнэ |
| `local_cleansession false` | bridge.conf | гүүрний **локал** талын session (гүүрт зориулсан дараалал) хадгалагдана. Заагаагүй бол `cleansession`-ий утгыг авна |
| `queue_qos0_messages true` | mosquitto.conf (**глобал**) | тогтвортой клиент (гүүр) тасарсан үед QoS 0 мессежийг ч дараалалд оруулна (MQTT стандарт биш сонголт); эдгээр нь `max_queued_messages`-д тоологдоно |

![Зураг 5.2 — Store-and-forward: холбоос тасрахад ирмэгийн Mosquitto мессежийг дараалалд хадгалж, сэргэхэд дахин илгээнэ](../docs/img/fig-bridge-saf.svg)

> **⚠ Тохиргооны урхи:** `bridge_queue_qos0_messages` гэсэн сонголт **байхгүй** — mosquitto үүнийг танихгүй сонголт гэж үзээд **огт эхлэхгүй**. Зөв нэр нь глобал `queue_qos0_messages`. Гүүрний хэсэгт бичих гэж оролдвол `docker compose logs mosquitto` дотор `Unknown configuration variable` гарна.

**Хүлээгдэх зан төлөв:** эдгээр гурав зөв тохируулагдсан үед **QoS 1**-ээр өгсөх урсгал унасан хугацаанд нийтэлсэн мессеж бүгд дараалалд орж, холбоос сэргэхэд үүл рүү урсана. Гэхдээ дөрвөн нарийн зүйл RPO/MTTR-ын тоонд шууд нөлөөлнө:

1. **Гүүр тасралтыг шууд мэддэггүй.** iptables DROP нь TCP холболтыг "тасалдаггүй" — пакетууд зүгээр л алга болно. Гүүр `keepalive_interval` (анхдагч **60 с**) хугацаанд юу ч ирээгүй бол PING илгээж, хариу ирэхгүй бол холболтыг хаана. Тэр болтол `bridge/state` = 1 хэвээр. Иймээс **60 секундын тасалдалд `bridge.jsonl` дээр "0" огт гарахгүй байж болно** (бидний туршилтаар keepalive 60 үед 60 с тасалдалд "0" гараагүй, keepalive 10 үед ~19 с-т илэрсэн). Тиймээс энэ лабд тасалдлын **бодит** цагийг `failure_inject.sh` бичдэг `uplink-events.jsonl`-ээс авна (`verify --cut-log`).
2. **QoS 0 ба илрүүлэх хугацаа.** Гүүр тасралтыг илрүүлэхээс өмнө TCP холболт руу бичигдсэн QoS 0 мессежийг дахин илгээх механизм байхгүй (QoS 0 = "хамгийн ихдээ нэг удаа"). Тиймээс `queue_qos0_messages true` байсан ч QoS 0-ийн алдагдал ≈ *хурд × илрүүлэх хугацаа* байж болно. QoS 1 мессеж PUBACK авах хүртэл session-д үлдэж, дахин холбогдоход дахин илгээгдэнэ.
3. **Дараалал дүүрэхэд ШИНЭ мессеж хаягдана.** Албан ёсны баримтаар хязгаарт хүрсний дараах мессежүүд "чимээгүй хаягдана" — хуучин нь үлдэнэ. mosquitto лог дээр `Outgoing messages are being dropped for client local.edge-…` гарна.
4. **Дараалал RAM-д байна.** `persistence true` үед санах ой дахь өгөгдөл `mosquitto.db` файлд зөвхөн (а) `autosave_interval` тутамд, (б) mosquitto **хэвийн** унтрахад, (в) `SIGUSR1` дохиогоор бичигдэнэ. `autosave_on_changes false` тул манай тохиргоонд 60 секунд тутамд. **Цахилгаан гэнэт тасарвал** (эсвэл SIGKILL) сүүлийн хадгалалтаас хойш дараалалд орсон мессеж алдагдана — энэ нь RPO-д шууд нэмэгдэнэ.

Гүүр тасарснаа мэдсэний дараа `restart_timeout 5 60`-ийн дагуу 5 секундээс эхлэн 60 секунд хүртэл санамсаргүй өсөх ("Decorrelated Jitter") завсарлагатайгаар дахин холбогдохыг оролдоно — энэ нь MTTR-д нэмэгдэнэ.

> Албан ёсны баримт: [mosquitto.conf(5)](https://mosquitto.org/man/mosquitto-conf-5.html) — `max_queued_messages`, `max_queued_bytes`, `queue_qos0_messages`, `persistence`, `autosave_interval`, `cleansession`, `local_cleansession`, `keepalive_interval`, `restart_timeout`.

---

## 4. Алхмууд

| Алхам | Хаана | Юу хийх | Мин | Хүснэгт |
|---|---|---|---|---|
| 1 | 💻 | InfluxDB бэлтгэх, бичилтийг гараар шалгах | 25 | 5.1 |
| 2 | 💻🥧 | Node-RED шугам ба Grafana самбар | 45 | 5.2 |
| 3 | 🥧 | Суурь бүрэн бүтэн байдал | 30 | 5.3 |
| 4 | 🥧 | Өгсөх урсгал тасрах: RPO ба MTTR | 60 | 5.4, 5.5 |
| 5 | 🥧 | `cleansession` ба дарааллын хязгаар | 35 | 5.6, 5.7 |
| 6 | 🥧💻 | Бусад эвдрэлүүд | 30 | 5.8 |
| 7 | 💻🥧 | Дүгнэлт ба Git | 15 | — |

---

### Алхам 1 — InfluxDB бэлтгэх ба бичилтийг гараар шалгах (25 мин) 💻

InfluxDB 3 нь *schema-on-write*: анхны бичилт өгөгдлийн сан, хүснэгтийг автоматаар үүсгэдэг. Гэхдээ санг **ил үүсгэх** нь сайн дадал (нэр, хадгалах хугацааг өөрөө шийднэ).

**1.1 Сан үүсгэж, жагсаах.**

**[💻 Ubuntu-1]**
```bash
curl -s -w '  → HTTP %{http_code}\n' -X POST 'http://localhost:8181/api/v3/configure/database' \
  -H 'Content-Type: application/json' -d '{"db":"cnc302"}'
curl -s 'http://localhost:8181/api/v3/configure/database?format=json' | jq
```

✅ `→ HTTP 200` (шинээр үүссэн) эсвэл `409` (Лаб 1-д аль хэдийн үүссэн) — **хоёулаа зүгээр**. Жагсаалтад `cnc302`.

**1.2 Нэг мөр гараар бичиж, буцааж унших.**

```bash
curl -s -w '  → HTTP %{http_code}\n' -X POST 'http://localhost:8181/api/v3/write_lp?db=cnc302&precision=millisecond' \
  -H 'Content-Type: text/plain' \
  --data-binary "telemetry,site=test,device=test0 temperature=24.5 $(date +%s%3N)"
curl -s -X POST 'http://localhost:8181/api/v3/query_sql' \
  -H 'Content-Type: application/json' \
  -d '{"db":"cnc302","q":"SELECT * FROM telemetry LIMIT 5","format":"json"}' | jq
curl -s 'http://localhost:8181/api/v3/query_sql?db=cnc302&format=jsonl&q=SELECT+*+FROM+telemetry+LIMIT+5'
```

✅ Бичилт `→ HTTP 204`; хоёр асуулга хоёулаа `"device":"test0"`, `"temperature":24.5` агуулсан мөр буцаана (сүүлийнх нь мөр бүр тусдаа JSON — `jsonl`).

- `precision` утга нь v3 API-д **бүтэн үгээр**: `auto` (анхдагч) | `nanosecond` | `microsecond` | `millisecond` | `second`. `ms`, `s` гэх товчлол нь зөвхөн v1 (`/write`) ба v2 (`/api/v2/write`) нийцлийн API-д хүчинтэй.
- Line protocol буруу эсвэл баганын төрөл зөрчигдвөл `400` ба алдааны JSON (анхдагч `accept_partial=true` үед зөв мөрүүд нь бичигдэнэ).
- `query_sql`-ийн `format`: `json` (анхдагч), `jsonl`, `csv`, `pretty`, `parquet`.
- **Нэвтрэлт:** манай стек `--without-auth`-аар ажилладаг (**зөвхөн лабораторид**). Бодит системд эхлээд `docker exec -it cnc302-influxdb influxdb3 create token --admin` гэж токен үүсгэж, бүх хүсэлтэд `-H "Authorization: Bearer $TOKEN"` толгой нэмнэ (`data_integrity.py verify --auth-token …`).

> Албан ёсны баримт: [InfluxDB 3 Core — v3 write_lp API](https://docs.influxdata.com/influxdb3/core/write-data/http-api/v3-write-lp/), [v3 query API](https://docs.influxdata.com/influxdb3/core/query-data/execute-queries/influxdb-v3-api/)

**1.3 Бичилтийн саатлыг хэмжих** (5 удаа, `%{time_total}` секундээр):

```bash
for i in 1 2 3 4 5; do curl -s -o /dev/null -w '%{time_total}\n' -X POST \
  'http://localhost:8181/api/v3/write_lp?db=cnc302&precision=millisecond' \
  -H 'Content-Type: text/plain' \
  --data-binary "telemetry,site=test,device=test0 temperature=2$i.0 $(date +%s%3N)"; done
```

✅ 5 мөр, жишээ `0.004215` (= 4.2 мс).

#### Хүснэгт 5.1 — Бичих давхаргын суурь

| Хэмжигдэхүүн | Утга | Тэмдэглэл |
|---|---|---|
| `write_lp` дундаж хугацаа (мс) | | 5 хэмжилтийн дундаж |
| `write_lp` хамгийн удаан (мс) | | |
| Хариу код (амжилттай бичилт) | | 204 хүлээгдэнэ |
| `query_sql` мөр буцаав уу | | |

> InfluxDB 2.7 нөөц хувилбар дээр ажиллаж байгаа бол `docs/troubleshooting.md` §6-г уншаад цаашид `verify`-д `--influx2` тугийг нэмнэ.

---

### Алхам 2 — Node-RED шугам ба Grafana самбар (45 мин) 💻🥧

![Зураг 5.1 — Өгөгдлийн шугам: EMQX → Node-RED (parse/validate → line protocol → HTTP write_lp) → InfluxDB 3 → Grafana, алдаатай мессеж dead-letter файл руу](../docs/img/fig-pipeline.svg)

```
mqtt in ─▶ задлах + шалгах ─┬─(1)─▶ line protocol (telemetry) ─┐
                            │  └──▶ 60с цонх ─▶ lp (нэгтгэл) ──┤
                            ├─(2)─▶ lp (integrity, rx_ms) ─────┼─▶ InfluxDB бичих ─▶ шалгах ─┬─▶ ok
                            └─(3)─▶ dead-letter ◀──────────────┘                            └─▶ dead-letter
```

`data_integrity.py`-ийн мессеж (`run_id`, `seq` талбартай) 2-р салаагаар `integrity` хүснэгтэд бичигдэнэ. Node-RED хүлээн авсан цаг `rx_ms` нь MTTR-ыг тооцоход хэрэглэгдэнэ.

**2.1 Урсгалыг Windows-ийн clipboard руу хуулах.** `clip.exe` нь WSL-ээс Windows-ийн clipboard руу бичнэ:

**[💻 Ubuntu-1]**
```bash
cat lab05/flows/nodered-pipeline.json | clip.exe
```

**2.2 Импортлох.** Windows-ийн хөтчөөр http://localhost:1880 →

1. Баруун дээд **☰** → **Import** (эсвэл `Ctrl + I`).
2. Том текст талбарт `Ctrl + V` (2.1-д хуулсан JSON).
3. Доод талд **new flow** сонго → **Import**.
4. Шинэ таб гарч ирнэ. Баруун дээд улаан **Deploy** товч.

✅ `Successfully deployed`. MQTT зангилааны доор ногоон **connected** гэсэн тэмдэг.

❌ **connected** биш, улаан **disconnected** → 2.3-ын `mqtt-broker` тохиргоо.

> Албан ёсны баримт: [Node-RED — Importing and Exporting Flows](https://nodered.org/docs/user-guide/editor/workspace/import-export)

**2.3 Хоёр зангилааг шалгах** (давхар товшиж нээнэ, **Done**-оор хаана):

| Зангилаа | Байх ёстой утга |
|---|---|
| `mqtt in` → брокер (харандаа дүрс) | Server `emqx`, Port `1883` (compose сүлжээн доторх нэр, `localhost` **биш**), Protocol **MQTT V5**, **Use clean start** унтраалттай, Session Expiry `3600` |
| `mqtt in` → Topic | `cnc302/+/+/+/+/telemetry` |
| `http request` | `POST`, URL `http://influxdb:8181/api/v3/write_lp?db=cnc302&precision=millisecond` |
| `http request` → **Only send non-2xx responses to Catch node** | **унтраалттай** — асаалттай бол InfluxDB унтарсан үеийн `ECONNREFUSED` гаралт руу гарахгүй, dead-letter хэзээ ч бичигдэхгүй |

Dead-letter файл `/data/deadletter.jsonl` — `nodered/node-red` дүрсийн хэрэглэгчийн хавтас `/data` бөгөөд `nodered-data` volume-д хадгалагдана. Ямар нэг утга өөрчилсөн бол дахин **Deploy**.

**2.4 Өгөгдөл урсгах.** Pi дээр агент:

**[🥧 Pi-2]**
```bash
cd ~/cnc302/edge && make agent
```

Компьютер дээр симулятор:

**[💻 Ubuntu-2]**
```bash
python tools/sim_device.py --target cloud --host localhost --devices 10 --interval 1
```

Node-RED-ийн баруун талын **debug** самбарыг (хорхойн дүрстэй таб) нээ.

✅ 10 секунд тутам `write_ok` тоолуур өснө. 2 минутын дараа `write_ok`, `write_errors`-ийг Хүснэгт 5.2-т бич.

**2.5 Задлах зангилааны гурван үүрэг** (`задлах + шалгах` function зангилааг давхар товшиж кодыг унш):

| Үүрэг | Код дотор | Яагаад |
|---|---|---|
| UNS схемийн шалгалт | `if (p.length !== 6)` | буруу нэршилтэй өгөгдөл санд орохгүй → dead-letter (`uns`) |
| Өгөгдлийн чанар | `temperature` / `proc_temp_c` `< -60 \|\| > 150` | эвдэрсэн мэдрэгч нэгтгэлийг сүйтгэнэ → dead-letter (`range:…`) |
| Шошго гаргах | `msg.tags = {site, area, line, device}` | InfluxDB-ийн tag (хэмжээс) |

Line protocol-д tag утгын **таслал, тэнцүүгийн тэмдэг, зай**-г `\`-ээр escape хийдэг (`esc()` функц); цаг нь миллисекунд тул URL-д `precision=millisecond`. Ижил хүснэгт + tag set + цагтай хоёр мөр нэг цэг болж нийлдэг тул QoS 1-ийн давхар хүргэлт санд давхар мөр үүсгэхгүй.

**2.6 Чанарын шүүлт ба dead-letter-ыг туршина.** Хүрээнээс гарсан утга — санд **ОРОХГҮЙ** байх ёстой:

**[💻 Ubuntu-1]**
```bash
mosquitto_pub -h localhost -t 'cnc302/shutis/mhts/lab/dev9999/telemetry' \
  -m '{"ts":'"$(date +%s%3N)"',"temperature":9999,"humidity":50,"vibration_rms":0.3}'
sleep 2
curl -s -X POST 'http://localhost:8181/api/v3/query_sql' -H 'Content-Type: application/json' \
  -d '{"db":"cnc302","q":"SELECT count(*) c FROM telemetry WHERE device='"'"'dev9999'"'"'","format":"json"}'
echo
docker exec cnc302-nodered wc -l /data/deadletter.jsonl
docker exec cnc302-nodered tail -1 /data/deadletter.jsonl
```

✅ `[{"c":0}]`; dead-letter-ийн сүүлийн мөр `{"stage":"parse","reason":"range:temperature",…}`.

❌ `No such file` (deadletter.jsonl) → dead-letter хараахан бичигдээгүй: 2.3-ын шалгалтыг дахин хий.

**2.7 Grafana самбар.** InfluxDB эх сурвалж аль хэдийн бүртгэгдсэн (query language **SQL**, database `cnc302`). SQL горимд Grafana нь InfluxDB 3 руу Flight SQL (gRPC)-ээр холбогддог тул TLS-гүй үед эх сурвалжийн **Insecure Connection** асаалттай байх ёстой.

1. http://localhost:3000 → **☰ → Connections → Data sources → InfluxDB3** → **Insecure Connection** асаалттай эсэхийг шалга → **Save & test** → ✅ ногоон.
2. **☰ → Dashboards → New → New dashboard → + Add visualization → InfluxDB3**.
3. Query засварлагчийг **SQL / Code** горимд шилжүүлж, доорх query-г буулга, баруун талаас Visualization төрлийг сонго, **Title** өг → **Back to dashboard**. Гурван панелийн хувьд давт:

| Title | Төрөл | Query |
|---|---|---|
| Температурын цуваа | Time series | `SELECT time, temperature, device FROM telemetry WHERE $__timeFilter(time) ORDER BY time` |
| Идэвхтэй төхөөрөмж | Stat | `SELECT count(DISTINCT device) AS devices FROM telemetry WHERE $__timeFilter(time)` |
| Бичилтийн хурд | Time series | `SELECT $__dateBin(time) AS time, count(*) AS points FROM telemetry WHERE $__timeFilter(time) GROUP BY 1 ORDER BY 1` |

4. **Save dashboard** → `Лаб 5 — Шугам`. Хугацааны мужийг **Last 15 minutes**, баруун дээд refresh-ийг **10s** болго.

✅ Гурван панелд өгөгдөл. Алхам 4-д өгсөх урсгал тасрахад энэ график дээр **цоорхой** үүсэх ёстой (эсвэл үүсэхгүй; аль нь болохыг та хэмжинэ).

`$__timeFilter(time)` нь самбарын цагийн хүрээг, `$__dateBin(time)` нь `date_bin()`-ийг Grafana-гийн `$__interval`-аар орлуулна. `GROUP BY time` (түүхий цагаар бүлэглэх) нь цэг бүрийг тусдаа бүлэг болгодог тул хурдыг харуулахгүй.

> Албан ёсны баримт: [Grafana — InfluxDB query editor (SQL macros)](https://grafana.com/docs/grafana/latest/datasources/influxdb/query-editor/), [Configure the InfluxDB data source](https://grafana.com/docs/grafana/latest/datasources/influxdb/configure/)

**2.8 Симулятор ба агентыг зогсоо** — Алхам 3-аас эхлэх хэмжилтэд саад болохгүй: **[💻 Ubuntu-2]** ба **[🥧 Pi-2]**-д `Ctrl + C`.

#### Хүснэгт 5.2 — Шугамын чанарын хяналт

| Хэмжигдэхүүн | Утга |
|---|---|
| `write_ok` (2 минутын дараа) | |
| `write_errors` | |
| Хүрээнээс гарсан утга санд оров уу | |
| `deadletter.jsonl`-ийн мөрийн тоо | |
| Grafana дээр өгөгдөл харагдав уу | |

---

### Алхам 3 — Суурь бүрэн бүтэн байдал: гүүрээр (30 мин) 🥧

Эвдрэлгүй үед **алдагдал 0%** байхыг эхлээд батал. Суурь дээр аль хэдийн алдагдаж байвал цааш явах утгагүй.

**3.1 Гүүрийн төлөвийг бичиж эхлэх — ЭНЭ ЦОНХЫГ ЭЦЭС ХҮРТЭЛ БҮҮ ХАА.**

**[🥧 Pi-1]**
```bash
mosquitto_sub -h localhost -F '{"ts":%U,"state":%p}' \
  -t "cnc302/$SITE/$AREA/$LINE/$DEVICE_ID/bridge/state" | tee lab05/out/bridge.jsonl
```

✅ Нэн даруй `{"ts":1791…,"state":1}` гэсэн мөр (retained) гарна. Цонх **нээлттэй хүлээж** байна.

❌ Юу ч гарахгүй → §2.2-ын блок энэ цонхонд буулгагдаагүй (`echo $DEVICE_ID` хоосон).

**3.2 Ирмэгийн брокер руу 3 минут нийтлэх** (10 мсж/с × 180 с = 1800 мессеж):

**[🥧 Pi-2]**
```bash
$PY lab05/data_integrity.py publish --via edge --host localhost \
    --rate 10 --seconds 180 --qos 1 --run-id base --outdir lab05/out
```

✅ 3 минутын дараа `илгээсэн: 1800` хэлбэрийн дүгнэлт.

**3.3 Шалгах.** InfluxDB нь **ҮҮЛ** дээр байгааг санаарай:

```bash
$PY lab05/data_integrity.py verify --influx "http://$CLOUD_HOST:8181" \
    --run-id base --outdir lab05/out
```

✅ «Алдагдал 0.0%», `lab05/out/base-result.json` үүснэ.

❌ `Connection refused` / timeout (8181) → компьютерийн галт хана (SETUP А.6) эсвэл InfluxDB асаагүй. ❌ Санд 0 мөр → Node-RED-ийн `integrity` салаа (Алхам 2.3), гүүр (`make link`).

#### Хүснэгт 5.3 — Суурь (эвдрэлгүй)

| Хэмжигдэхүүн | Утга |
|---|---|
| Илгээсэн (амжилттай) | |
| Санд олдсон | |
| Алдагдал % | 0.0 байх ЁСТОЙ |
| Холболтын тасалдал | |
| Хамгийн урт тасалдал (мессеж / сек) | / |

---

### Алхам 4 — ӨГСӨХ УРСГАЛ (UPLINK) ТАСРАХ: RPO ба MTTR (60 мин) 🥧

**Энэ бол лабораторийн гол хэсэг.** `uplink-down` нь Pi → үүл чиглэлийн 1883 портыг л хаана (iptables `OUTPUT … -j DROP`, iptables байхгүй бол nft `inet cnc302` хүснэгт): ирмэгийн mosquitto ажилласаар, төхөөрөмжүүд Pi руу нийтэлсээр байна. Энэ нь «бүх зүйл унасан» биш, яг **өгсөх урсгал тасарсан** туршилт.

**Туршилт бүрийн хэв маяг (4.1, 4.4, 4.5, 5.x, 6.x-д ижил):**

1. **[🥧 Pi-3]** `sudo -v` — sudo нууц үгийг урьдчилан оруулна (15 мин хадгалагдана; эс бөгөөс `sleep`-ийн дараа нууц үг асууж, тасалдал хоцорно).
2. **[🥧 Pi-2]** `publish` эхлүүлнэ.
3. **[🥧 Pi-3]** `sleep N && bash lab05/failure_inject.sh …` — эвдрэл.
4. Хоёулаа дуусахыг хүлээнэ, **30 сек** нэмж хүлээнэ (дараалал урсаж дуусна).
5. **[🥧 Pi-2]** `verify`.

**4.1 QoS 1, 60 секундын тасалдал** (нийт ≈ 5.5 мин):

**[🥧 Pi-3]**
```bash
sudo -v
```

**[🥧 Pi-2]** — 5 минут нийтэлнэ:
```bash
$PY lab05/data_integrity.py publish --via edge --host localhost \
    --rate 10 --seconds 300 --qos 1 --run-id uplink60 --outdir lab05/out
```

**[🥧 Pi-3]** — **шууд дараа нь**; 60 секундын дараа өгсөх урсгалыг 60 секунд таслана:
```bash
sleep 60 && bash lab05/failure_inject.sh uplink-down 60
```

✅ `▼ …` (тасалсан) ба 60 сек дараа `▲ Өгсөх урсгал сэргэлээ.` `failure_inject.sh` тасалдлын эхлэл/төгсгөлийг `lab05/out/uplink-events.jsonl`-д бичнэ.

Энэ үед юу болдгийг Зураг 5.2-оос дахин хар.

**4.2 Тасалдлын ҮЕД дараалал өсөж байгааг харах.** Тасарсан 60 секундын дотор — **[🥧 Pi-3]**-ийн `sleep` дуусахыг хүлээх хооронд **шинэ** PowerShell таб → `ssh pi` нээж:

```bash
mosquitto_sub -h localhost -t '$SYS/broker/store/messages/count' -C 1
docker stats --no-stream cnc302-mosquitto
```

(10 сек тутам шинэчлэгддэг; хоёр гурван удаа давт.) Хадгалагдсан мессежийн тоо ба mosquitto-гийн RAM өсч байна уу? Хуучин хувилбарт сэдэв нь `$SYS/broker/messages/stored`.

Гүүр тасралтыг хэзээ илрүүлснийг **[🥧 Pi-1]**-ийн `bridge.jsonl`-ээс хар — `uplink-down`-оос хэдэн секундын дараа `"state":0` гарав (эсвэл огт гарсангүй)? Энэ зөрүүг Хүснэгт 5.5-д бич.

> **Урхинд бүү ор.** Өгсөх урсгал сэргэсний дараа шинэ `mosquitto_sub` асаавал дахин илгээгдсэн мессеж **харагдахгүй** — тэсрэлт аль хэдийн өнгөрсөн байна. Дахин илгээлтийн нотолгоо нь зөвхөн (а) InfluxDB дэх мөрүүд, (б) Алхам 3-аас хойш тасралтгүй ажиллаж байгаа `bridge.jsonl` хоёр.

**4.3 Шалгах — алдагдлыг гүүрний төлөвөөр ХУВААНА.** `publish` дуусмагц, 30 сек хүлээгээд:

**[🥧 Pi-2]**
```bash
sleep 30
$PY lab05/data_integrity.py verify --influx "http://$CLOUD_HOST:8181" \
    --run-id uplink60 --outdir lab05/out --bridge-log lab05/out/bridge.jsonl \
    --cut-log lab05/out/uplink-events.jsonl
```

✅ Гаралт нь алдагдлыг хоёр янзаар хуваана: (а) **гүүрийн мэдээлсэн** төлөвөөр (`--bridge-log`), (б) **бодит** тасалдлаар (`--cut-log`), мөн MTTR-ыг (`mttr_s`) автоматаар тооцно. Хоёр хуваалтын «тасарсан (с)» ялгаа нь гүүрийн илрүүлэх хугацаа юм.

**4.4 QoS 0-оор давт** — 4.1–4.3-ыг яг ижил дарааллаар, зөвхөн `--qos 0 --run-id uplink60q0`:

**[🥧 Pi-2]**
```bash
$PY lab05/data_integrity.py publish --via edge --host localhost \
    --rate 10 --seconds 300 --qos 0 --run-id uplink60q0 --outdir lab05/out
```

**[🥧 Pi-3]**
```bash
sudo -v; sleep 60 && bash lab05/failure_inject.sh uplink-down 60
```

**[🥧 Pi-2]** (дууссаны дараа)
```bash
sleep 30
$PY lab05/data_integrity.py verify --influx "http://$CLOUD_HOST:8181" \
    --run-id uplink60q0 --outdir lab05/out --bridge-log lab05/out/bridge.jsonl \
    --cut-log lab05/out/uplink-events.jsonl
```

**4.5 Тасалдлыг уртасга** — 3 минут (нийт ≈ 7.5 мин): **[🥧 Pi-2]** `… --qos 1 --seconds 420 --run-id uplink180 …`, **[🥧 Pi-3]** `sudo -v; sleep 60 && bash lab05/failure_inject.sh uplink-down 180`, дараа нь `verify --run-id uplink180 …` (бусад тугууд 4.3-тай ижил).

#### Хүснэгт 5.4 — Өгсөх урсгал тасрах: RPO ба MTTR ⭐

| Ажиллалт | QoS | Тасалдал (с) | Илгээсэн | Санд хүрсэн | Алдагдал % | **RPO (с)** | **MTTR (с)** | Гүүр дахин холбогдох хугацаа (с) |
|---|---|---|---|---|---|---|---|---|
| `uplink60` | 1 | 60 | | | | | | |
| `uplink60q0` | 0 | 60 | | | | | | |
| `uplink180` | 1 | 180 | | | | | | |

- **RPO** = хамгийн урт тасалдлын хугацаа (`verify`-ийн «Хамгийн урт тасалдал ... секунд»). Алдагдал 0 бол RPO = 0.
- **MTTR** = өгсөх урсгал сэргэснээс (`uplink-events.jsonl`-ийн `state=1`) тасалдлын үеэр илгээсэн сүүлийн мессеж санд хүрэх (`integrity.rx_ms`) хүртэлх хугацаа — `verify --cut-log` хэвлэнэ (`mttr_s`).
- **Гүүр дахин холбогдох хугацаа** = `bridge.jsonl`-ийн `state=1` − `uplink-events.jsonl`-ийн `state=1` (хоёулаа мс; **[🥧 Pi-3]** `tail -4 lab05/out/uplink-events.jsonl lab05/out/bridge.jsonl`).

#### Хүснэгт 5.5 — Бодит тасалдал ба гүүрийн мэдээлсэн төлөвөөр хуваасан алдагдал (`--cut-log`, `--bridge-log`)

| Ажиллалт | Бодит тасалдал (с, `--cut-log`) | Гүүрийн мэдээлсэн тасалдал (с, `--bridge-log`) | Илрүүлэх хугацаа (с) | Бодит тасалдлын үед: илгээсэн / алдагдсан / % | Ажиллаж байхад: илгээсэн / алдагдсан / % |
|---|---|---|---|---|---|
| `uplink60` (QoS 1) | | | | / / | / / |
| `uplink60q0` (QoS 0) | | | | / / | / / |
| `uplink180` (QoS 1) | | | | / / | / / |

> **Хүлээгдэх үр дүн:** `cleansession false` + `local_cleansession false` + `queue_qos0_messages true` үед **QoS 1**-ийн алдагдал 0% байх ёстой — PUBACK аваагүй мессеж session-д үлдэж, дахин холбогдоход илгээгдэнэ. **QoS 0**-д гүүр тасралтыг илрүүлэхээс өмнө TCP руу бичигдсэн мессеж алдагдаж болно (§3, 2-р зүйл) — алдагдсан хэсэг тасалдлын **эхэнд** байвал яг энэ шалтгаан. 60 секундын тасалдалд гүүр «0» мэдээлээгүй байж болохыг анхаар (keepalive 60 с).

---

### Алхам 5 — `cleansession` ба дарааллын хязгаар (35 мин) 🥧

**5.1 `cleansession` ба `local_cleansession`-ийг салгаж турш.** `bridge.conf`-д `local_cleansession false` **ил** бичигдсэн тул зөвхөн `cleansession`-ийг `true` болгох нь гүүрний **локал** дарааллыг хөндөхгүй — энэ хоёрын үүргийг ялгах нь энэ алхмын зорилго.

> ⚠ `make restart` нь эхлээд `make bridge`-ийг ажиллуулж `bridge.conf`-ыг **загвараас дахин үүсгэдэг** — гар засвар устана. Тиймээс энд `docker compose restart mosquitto`. Дуусаад 5.4-т `make bridge`-ээр анхны төлөвт буцаана.

**(а) Зөвхөн алсын тал цэвэр.** `sed` нь файлд засвар хийнэ (nano-гаар гараар засаж болно):

**[🥧 Pi-3]**
```bash
cd ~/cnc302/edge
sed -i 's/^cleansession .*/cleansession true/; s/^local_cleansession .*/local_cleansession false/' mosquitto/conf.d/bridge.conf
grep -E '^(cleansession|local_cleansession)' mosquitto/conf.d/bridge.conf
docker compose restart mosquitto
sleep 5; docker compose logs --tail=20 mosquitto | grep -i bridge
cd ~/cnc302
```

✅ `cleansession true` / `local_cleansession false`; логт `Connecting bridge cloud`.

Дараа нь Алхам 4.1–4.3-ыг `--run-id uplink60clean`-ээр давт.

**(б) Хоёр тал цэвэр.**

**[🥧 Pi-3]**
```bash
cd ~/cnc302/edge
sed -i 's/^cleansession .*/cleansession true/; s/^local_cleansession .*/local_cleansession true/' mosquitto/conf.d/bridge.conf
grep -E '^(cleansession|local_cleansession)' mosquitto/conf.d/bridge.conf
docker compose restart mosquitto
cd ~/cnc302
```

Алхам 4.1–4.3-ыг `--run-id uplink60cleanboth`-оор давт.

> ⚠️ `docker compose restart mosquitto` хийхэд **[🥧 Pi-1]**-ийн `mosquitto_sub` тасарч болно. Тасарсан бол 3.1-ийн командыг `tee` биш **`tee -a`**-аар (файлыг дарж бичихгүйн тулд) дахин асаа.

> Бидний урьдчилсан туршилтаар (mosquitto 2.0, QoS 1, 30 с тасалдал) (а) алдагдалгүй, (б) тасалдлын үеийн мессеж бараг бүгд алдагдсан. Өөрсдийн тоогоор батал.

**5.2 Дарааллын RAM-ын арифметик.** `mosquitto.conf` дахь `max_queued_messages 100000` юу гэсэн үг вэ — тоол:

```
100 000 мессеж × ______ Б (таны ачаалал) = ______ MiB
Pi-гийн боломжтой RAM (Лаб 4, Хүснэгт 4.1) = ______ MiB
→ Дараалал бүрэн дүүрэхэд Pi амьд үлдэх үү: ______
→ Таны хурдаар (______ мсж/с) дараалал дүүрэхэд ______ секунд шаардагдана
```

**5.3 Дарааллын халилтыг үзэх.** Эхлээд гүүрийг **анхны** тохиргоонд буцааж, дараа нь дарааллын хязгаарыг зориудаар 500 болгоно. `max_queued_messages` нь «дамжуулж байгаа (in-flight) мессежээс **гадна**» хадгалах QoS 1/2 мессежийн тоо (клиент тус бүрд):

**[🥧 Pi-3]**
```bash
cd ~/cnc302/edge
make bridge
sed -i 's/^max_queued_messages .*/max_queued_messages 500/' mosquitto/mosquitto.conf
grep '^max_queued_messages' mosquitto/mosquitto.conf
docker compose restart mosquitto
cd ~/cnc302
```

✅ `max_queued_messages 500`.

Одоо 120 сек таслаад 10 мсж/с илгээнэ → 1200 мессеж > 500 дараалал:

**[🥧 Pi-2]**
```bash
$PY lab05/data_integrity.py publish --via edge --host localhost \
    --rate 10 --seconds 240 --qos 1 --run-id qfull --outdir lab05/out
```

**[🥧 Pi-3]**
```bash
sudo -v; sleep 30 && bash lab05/failure_inject.sh uplink-down 120
docker compose -f ~/cnc302/edge/docker-compose.yml logs mosquitto | grep -i "dropped" | tail -5
```

**[🥧 Pi-2]** (дууссаны дараа)
```bash
sleep 30
$PY lab05/data_integrity.py verify --influx "http://$CLOUD_HOST:8181" \
    --run-id qfull --outdir lab05/out --bridge-log lab05/out/bridge.jsonl \
    --cut-log lab05/out/uplink-events.jsonl
```

Алдагдсан `seq`-ийн хүрээ тасалдлын **эхэнд** үү, **төгсгөлд** үү гэдгийг `verify`-ийн тасралтын жагсаалтаас ол.

**5.4 БУЦААЖ анхны тохиргоонд — ЗААВАЛ.**

**[🥧 Pi-3]**
```bash
cd ~/cnc302/edge
sed -i 's/^max_queued_messages .*/max_queued_messages 100000/' mosquitto/mosquitto.conf
make bridge
docker compose restart mosquitto
grep '^max_queued_messages' mosquitto/mosquitto.conf
grep -E '^(cleansession|local_cleansession)' mosquitto/conf.d/bridge.conf
cd ~/cnc302
```

✅ `100000`, `cleansession false`, `local_cleansession false`. `git diff edge/mosquitto/mosquitto.conf` хоосон.

#### Хүснэгт 5.6 — `cleansession` ба дарааллын хязгаарын харьцуулалт

| Тохиргоо | Гүүр унасан үед илгээсэн | Алдагдсан | Алдагдал % | Дараалал хадгалагдав уу |
|---|---|---|---|---|
| `cleansession false`, `local_cleansession false`, дараалал 100000 (үндсэн) | | | | |
| `cleansession true`, `local_cleansession false`, дараалал 100000 | | | | |
| `cleansession true`, `local_cleansession true`, дараалал 100000 | | | | |
| `cleansession false`, дараалал 500 | | | | |

#### Хүснэгт 5.7 — Дарааллын нөөцийн зардал

| Асуулт | Хариулт |
|---|---|
| Нэг мессежийн бодит хэмжээ (Б) | |
| 100 000 мессежийн RAM (MiB) | |
| Дараалал дүүрэх хугацаа таны хурдаар (с) | |
| Дараалал өсөх үед mosquitto-гийн RAM хэдээр өсөв (MiB) | |
| Дараалал халихад аль мессеж хаягдав (хуучин уу, шинэ үү) | |

**5.5 microSD-гийн бичих саатал.** mosquitto-гийн persistence ба InfluxDB хоёулаа диск рүү бичдэг. Pi-гийн картыг хэмж (4 KiB × 2000 синхрон бичилт):

**[🥧 Pi-3]**
```bash
dd if=/dev/zero of=~/cnc302/sdtest bs=4k count=2000 oflag=dsync 2>&1 | tail -1
rm ~/cnc302/sdtest && vmstat 1 5
```

✅ Эхний команд `8192000 bytes … copied, N s, X kB/s`; `vmstat`-ын `wa` багана = I/O хүлээлт.

Гарсан тоог `autosave_interval 60`-той холбож тайлбарла: mosquitto яагаад бичилт бүрийг шууд диск рүү буулгадаггүй вэ, энэ нь тасалдал үед юу алдах эрсдэлтэй вэ? Хариултаа Алхам 6-гийн `broker` (хэвийн зогсоолт → `mosquitto.db` бичигдэнэ) ба `broker-kill` (SIGKILL → бичигдэхгүй) хоёрын үр дүнгээр батал.

---

### Алхам 6 — Бусад эвдрэлүүд (30 мин) 🥧💻

Тус бүрд Алхам 4-ийн **хэв маягийг** дагана: **[🥧 Pi-2]** `publish` (`--seconds 180`, шинэ `--run-id`) → **[🥧 Pi-3]** 60 сек дараа эвдрэл → дууссаны дараа 30 сек хүлээгээд `verify --run-id … --bridge-log lab05/out/bridge.jsonl`. `run-id`-г доорх хүснэгтийн дагуу нэрлэ.

| run-id | Хаана | Эвдрэлийн команд (60 сек дараа) | Юу хийдэг вэ |
|---|---|---|---|
| `broker30` | **[🥧 Pi-3]** | `bash lab05/failure_inject.sh broker 30` | ирмэгийн mosquitto өөрөө унана — гүүр биш, **БРОКЕР** (хэвийн SIGTERM → `mosquitto.db` хадгалагдана) |
| `kill20` | **[🥧 Pi-3]** | `bash lab05/failure_inject.sh uplink-down 120 &` → 40 сек дараа `bash lab05/failure_inject.sh broker-kill 20` | цахилгаан тасрахыг дуурайна: өгсөх урсгал тасарсан **ҮЕД** mosquitto-г SIGKILL-ээр унагана |
| `influx30` | **[💻 Ubuntu-1]** | `bash lab05/failure_inject.sh influx 30` | **ҮҮЛ** дээр: InfluxDB унана. Брокер, гүүр ажилласаар байна! |
| `cpu45` | **[🥧 Pi-3]** | `bash lab05/failure_inject.sh cpu 45` | CPU ханалт (дулааны төсөв ч мөн шалгагдана) |
| `disk60` | **[🥧 Pi-3]** | `bash lab05/failure_inject.sh disk 60` | **АЮУЛГҮЙ** дискний туршилт — `/dev/shm` (RAM) дээрх 64 MiB loop файл, бодит microSD хөндөгдөхгүй |

- `broker`, `broker-kill` үед **[🥧 Pi-1]**-ийн `mosquitto_sub` тасарна — дууссаны дараа 3.1-ийн командыг **`tee -a`**-аар дахин асаа.
- `influx30`-ийн дараа dead-letter ажилласан эсэхийг шалга: **[💻 Ubuntu-1]** `docker exec cnc302-nodered wc -l /data/deadletter.jsonl` (өмнөхөөс өссөн үү?).

**Эцэст нь БҮГДИЙГ сэргээнэ** — хоёр хост дээр:

**[🥧 Pi-3]**
```bash
bash lab05/failure_inject.sh restore
```

**[💻 Ubuntu-1]**
```bash
bash lab05/failure_inject.sh restore
cd ~/cnc302/stack && make health && cd ~/cnc302
```

✅ Pi: `cnc302-mosquitto … Up`; компьютер: `make health` дөрвөн мөр `200`.

> `influx` горим нь хамгийн заль мэхтэй тохиолдол: **төхөөрөмж юу ч анзаарахгүй**, брокер хүлээж авсаар байна, гүүр ажиллаж байна — гэвч өгөгдөл хаана ч хадгалагдахгүй. Ийм эвдрэлийг зөвхөн Node-RED-ийн `write_errors` тоолуур ба dead-letter файлаас л илрүүлнэ. Grafana дээр график тасарна — гэхдээ хэн нэг нь харж байвал л.

#### Хүснэгт 5.8 — ЭВДРЭЛИЙН МАТРИЦ ⭐

| # | Эвдрэл | Үргэлжлэл (с) | Шинж тэмдэг | Илгээсэн | Санд хүрсэн | Алдагдал % | RPO (с) | MTTR (с) | Автоматаар сэргэв үү |
|---|---|---|---|---|---|---|---|---|---|
| 0 | Суурь (эвдрэлгүй) | — | | | | | | | |
| 1 | `uplink-down`, QoS 1 | 60 | | | | | | | |
| 2 | `uplink-down`, QoS 0 | 60 | | | | | | | |
| 3 | `uplink-down`, QoS 1 | 180 | | | | | | | |
| 4 | `cleansession true` (+ `local_cleansession true`) | 60 | | | | | | | |
| 5 | Дараалал 500 (халилт) | 120 | | | | | | | |
| 6 | `broker` (ирмэгийн mosquitto, SIGTERM) | 30 | | | | | | | |
| 6б | `broker-kill` өгсөх урсгал тасарсан үед (SIGKILL) | 20 | | | | | | | |
| 7 | `influx` (үүлний сан) | 30 | | | | | | | |
| 8 | `cpu` | 45 | | | | | | | |
| 9 | `disk` | 60 | | | | | | | |

---

### Алхам 7 — Дүгнэлт ба Git (15 мин) 💻🥧

Багийн төслийн **найдвартай байдлын паспорт**-ыг бич: ямар RPO, ямар MTTR-ыг зорилт болгох вэ, түүнд хүрэхийн тулд ямар тохиргоо шаардлагатай вэ (`max_queued_messages`, `cleansession`, QoS, диск).

**7.1 Pi бүрэн хэвийн байгааг батлах.** **[🥧 Pi-1]**-д `Ctrl + C` (гүүрийн бичлэгийг зогсооно), дараа нь:

**[🥧 Pi-3]**
```bash
bash lab05/failure_inject.sh restore
git status --short edge/
```

✅ `edge/` дотор өөрчлөгдсөн файл **алга** (5.4-т буцаасан).

**7.2 Үр дүнг компьютер руу хуулах.** `verify`-ийн үр дүн Pi дээр бичигдсэн:

**[💻 Ubuntu-1]**
```bash
cd ~/cnc302
scp -i ~/.ssh/cnc302 'cnc302@<PI_IP>:cnc302/lab05/out/*-result.json' \
    'cnc302@<PI_IP>:cnc302/lab05/out/*.jsonl' 'cnc302@<PI_IP>:cnc302/lab05/out/failure-log.txt' lab05/out/
ls lab05/out/*-result.json
```

✅ `base-result.json`, `uplink60-result.json`, … бүгд.

**7.3 Тайлан, нэмэх, шалгах.** `lab05/out/` нь `.gitignore`-д — зөвхөн үр дүнгийн JSON-г **зориуд** нэмнэ (том `-sent.jsonl`-уудыг БИШ):

```bash
cp docs/report-template.md lab05/report.md
code lab05/report.md
git add lab05/report.md
git add -f lab05/out/*-result.json lab05/out/failure-log.txt
git status --short
git ls-files | grep -E '\.env$|bridge\.conf$|\.key$|\.crt$|devices\.csv'
```

✅ Сүүлийн команд **юу ч хэвлэхгүй**.

**7.4 Commit ба push.**
```bash
git commit -m "Лаб 5: өгөгдлийн шугам, өгсөх урсгал тасрах, RPO/MTTR"
git tag lab05-done
git push && git push --tags
```

---

## 5. Хяналтын асуултууд

1. Хүснэгт 5.5-д QoS 1 үед **бодит тасалдлын** хугацаанд илгээсэн хэдэн мессежээс хэд нь алдагдав? Хэрэв 0 бол аль тохиргоо үүнийг боломжтой болгов? Хүснэгт 5.6-гийн 2 ба 3-р мөрийн ялгаагаар `cleansession` ба `local_cleansession`-ийн үүргийг тайлбарла.

2. Хүснэгт 5.4-т QoS 0 ба QoS 1-ийн алдагдал хэдээр зөрөв? `queue_qos0_messages true` байхад ялгаа бага гарсан бол энэ нь юуг харуулж байна вэ?

3. Хүснэгт 5.4-т таны RPO ба MTTR тус бүр хэдэн секунд гарав? Аль нь илүү муу вэ, яагаад? Хэрэв мессеж бүгд хүрсэн ч 40 секунд хоцорч ирсэн бол энэ ямар хэрэглээнд хүлээн зөвшөөрөгдөх, ямарт нь болохгүй вэ?

4. Хүснэгт 5.7-д `max_queued_messages 100000` хэдэн MiB шаардаж байна? Pi 3B-гийн үлдэгдэл RAM (Лаб 4, Хүснэгт 4.1)-тай харьцуулахад энэ аюулгүй тоо мөн үү? Та ямар утга сонгох вэ, яагаад?

5. Дараалал 500 болгосон туршилтад (Хүснэгт 5.6) аль мессежүүд алдагдав — эхнийх нь үү, сүүлийнх нь үү? Энэ нь дарааллын халилтын бодлогын талаар юу хэлж байна вэ, таны хэрэглээнд аль нь дээр вэ?

6. `influx` эвдрэлийн үед төхөөрөмж юу ч анзаарсангүй. Хүснэгт 5.8-ын 7-р мөрөнд хэдэн мессеж алдагдав, dead-letter-т хэдэн мөр орсон бэ? Ийм "чимээгүй" эвдрэлийг хэдэн секундын дотор илрүүлэх систем хэрхэн барих вэ?

7. `dd … oflag=dsync` хэмжилтэд microSD хэдэн MB/с, нэг бичилт дунджаар хэдэн мс байв? Энэ тоо mosquitto-гийн `autosave_interval 60` ба InfluxDB-ийн бичилтэд хэрхэн нөлөөлж байна вэ? Хүснэгт 5.8-ын 6 ба 6б мөрийн ялгааг `autosave_interval`-аар тайлбарла.

8. Хүснэгт 5.5-д гүүр тасралтыг хэдэн секундын дараа илрүүлэв? `keepalive_interval`-ийг 60-аас 15 болговол RPO (QoS 0) ба MTTR хэрхэн өөрчлөгдөх вэ, ямар зардалтай вэ?

---

## 6. Хүлээлгэн өгөх зүйл

| # | Зүйл | Байрлал |
|---|---|---|
| 1 | Тайлан (Хүснэгт 5.1–5.8 бөглөсөн) | `lab05/report.md` → PDF |
| 2 | `verify`-ийн үр дүнгийн JSON файлууд | `lab05/out/*-result.json` |
| 3 | Node-RED урсгалын экспорт (өөрчилсөн бол) | `lab05/flows/` |
| 4 | Grafana самбар — тасалдлын цоорхой харагдсан зураг | тайлангийн хавсралт |
| 5 | Багийн найдвартай байдлын паспорт (RPO/MTTR зорилт) | тайлангийн хавсралт |
| 6 | Git tag | `lab05-done` |

---

## 7. Үнэлгээний шалгуур (10 оноо)

| Шалгуур | Оноо |
|---|---|
| Шугам бүрэн ажиллаж, чанарын шүүлт ба dead-letter баталгаажсан | 2 |
| Өгсөх урсгалын тасалдлын гурван ажиллалт хийгдэж, Хүснэгт 5.4–5.5 бүрэн | 3 |
| **RPO ба MTTR тоогоор, InfluxDB-ийн нотолгоотойгоор** гаргасан | 2 |
| `cleansession` ба дарааллын хязгаарын харьцуулалт (5.6–5.7) | 2 |
| Эвдрэлийн матриц бүрэн, систем цэвэр сэргээгдсэн | 1 |

**Онцгой оноо (+1):** дахин илгээлтийг тогтвортой session-тэй захиалагчаар (эсвэл өөр аргаар) InfluxDB-ээс гадна бие даан баталсан бол.

---

## 8. Түгээмэл алдаа

| Шинж | Шалтгаан | Шийдэл |
|---|---|---|
| Дахин илгээлт "харагдахгүй" | `mosquitto_sub` тэсрэлтийн ДАРАА асаасан | InfluxDB-ээс шалга (Алхам 4.2-ын урхи) |
| mosquitto огт эхлэхгүй | `bridge_queue_qos0_messages` гэж бичсэн | глобал `queue_qos0_messages`-ыг ашигла |
| Node-RED `400` буцаана | line protocol буруу эсвэл баганын төрөл зөрчигдсөн (жишээ: нэг талбарт тоо, дараа нь текст) | `deadletter.jsonl`-ийн `error` ба `lp`-г хар |
| `write_errors` өсөж, код нь `ECONNREFUSED`/`ENOTFOUND` | InfluxDB унтарсан эсвэл хаяг буруу | `docker compose ps influxdb`, URL `http://influxdb:8181` |
| InfluxDB унтарсан ч dead-letter хоосон | `http request`-ийн "Only send non-2xx responses to Catch node" асаалттай | сонголтыг унтраа (Алхам 2.3) |
| `bridge.jsonl`-д `0` гарсангүй | тасалдал `keepalive_interval`-аас богино | `--cut-log`-оор шалга (Алхам 4.3) |
| `verify` 0 мөр олно | буруу `--influx` эсвэл `--db` | `SELECT * FROM integrity LIMIT 5` |
| Суурь тестэд аль хэдийн алдагдал | сэдвийн угтвар `SITE`-тай зөрсөн | troubleshooting §2 |
| `uplink-down` → эрхийн алдаа | iptables/nft-д sudo эрх хэрэгтэй | `sudo bash lab05/failure_inject.sh uplink-down 60` |
| `bridge.conf` засвар алга болов | `make restart` загвараас дахин үүсгэсэн | `docker compose restart mosquitto` ашигла |
| `disk` горим `mount` алдаа | sudo эрхгүй эсвэл loop модуль алга | эхлээд `sudo -v` |
| Сэргэсний дараа гүүр удаан холбогдоно | `restart_timeout 5 60` backoff | 60 секунд хүртэл хүлээ, `make link`-ээр хар |
| `verify`: `table 'integrity' not found` | урсгалын хуучин хувилбар импортлогдсон (integrity салаагүй) | `lab05/flows/nodered-pipeline.json`-ийг дахин импортло |
| `No module named 'requests'` / `'paho'` (Pi) | ирмэгийн venv-д алга / `python3` гэж бичсэн | §2.3, `$PY` |
| `verify`: `Connection refused` (8181) | компьютерийн галт хана эсвэл InfluxDB унтарсан | SETUP А.6; 💻 `make health` |
| Эвдрэл `sleep`-ийн дараа нууц үг асууж хоцров | sudo нууц үг кэшлэгдээгүй | эвдрэлийн өмнө `sudo -v` (Алхам 4) |
| Node-RED Import-д `Ctrl+V` юу ч буулгахгүй | `clip.exe` ажиллаагүй | `\\wsl$\Ubuntu\home\<нэр>\cnc302\lab05\flows\` хавтаснаас файлыг **select a file to import**-оор сонго |
| `bridge.jsonl` дахин асаахад хуучин бичлэг устав | `tee` (`-a`-гүй) файлыг дарж бичсэн | `tee -a` (Алхам 5.1, 6) |
| Лабын дараа гүүр/дараалал хачин | 5.x-ийн тохиргоо буцаагдаагүй | Алхам 5.4 |

---

## 9. Эх сурвалж

| # | Эх сурвалж | Юуг баталгаажуулсан | Хандсан |
|---|---|---|---|
| 1 | [mosquitto.conf(5)](https://mosquitto.org/man/mosquitto-conf-5.html) | `persistence`, `autosave_interval`, `autosave_on_changes` (зөвхөн autosave/унтрах/SIGUSR1 үед бичнэ), `max_queued_messages` (in-flight-аас гадна, анхдагч 1000), `max_queued_bytes` (хязгаарт хүрвэл дараагийн мессеж чимээгүй хаягдана), `queue_qos0_messages` (глобал, стандарт биш), `cleansession`, `local_cleansession`, `keepalive_interval` (анхдагч 60), `restart_timeout` (base/cap, jitter), `notifications`, `notification_topic` | 2026-09 |
| 2 | [mosquitto(8)](https://mosquitto.org/man/mosquitto-8.html) | `$SYS/broker/store/messages/count` (хуучин нэр `messages/stored`), `$SYS/broker/connection/#`, `sys_interval` | 2026-09 |
| 3 | [mosquitto_sub(1)](https://mosquitto.org/man/mosquitto_sub-1.html) | `-F` формат, `%U` (наносекундтэй Unix цаг), `%p` | 2026-09 |
| 4 | [InfluxDB 3 Core — Use the v3 write_lp API](https://docs.influxdata.com/influxdb3/core/write-data/http-api/v3-write-lp/) | `precision` утгууд (`auto`/`nanosecond`/`microsecond`/`millisecond`/`second`), `accept_partial`, `no_sync`, 204/400 хариу | 2026-09 |
| 5 | [InfluxDB 3 Core API — Write data](https://docs.influxdata.com/influxdb3/core/api/write-data/) | v1/v2/v3 precision харьцуулалт (`ms` зөвхөн v1/v2), 204/400/401/403/413 | 2026-09 |
| 6 | [InfluxDB 3 Core — Use the v3 query API](https://docs.influxdata.com/influxdb3/core/query-data/execute-queries/influxdb-v3-api/) | `/api/v3/query_sql` GET/POST, `db`, `q`, `format` (json/jsonl/csv/pretty/parquet) | 2026-09 |
| 7 | [InfluxDB 3 Core — Create a database](https://docs.influxdata.com/influxdb3/core/admin/databases/create/), [API — Database](https://docs.influxdata.com/influxdb3/core/api/database/) | `POST /api/v3/configure/database` (`{"db":…}`, 200/409), `GET …?format=json` | 2026-09 |
| 8 | [InfluxDB 3 Core — Write data (get started)](https://docs.influxdata.com/influxdb3/core/get-started/write/) | schema-on-write: сан, хүснэгт автоматаар үүснэ | 2026-09 |
| 9 | [InfluxDB 3 Core — Line protocol](https://docs.influxdata.com/influxdb3/core/reference/line-protocol/) | escape дүрэм (tag утга: таслал, `=`, зай), `i` бүхэл тоо, давхар цэг нийлэх | 2026-09 |
| 10 | [InfluxDB 3 Core — Configuration options](https://docs.influxdata.com/influxdb3/core/reference/config-options/), [Set up Core](https://docs.influxdata.com/influxdb3/core/get-started/setup/), [API authentication](https://docs.influxdata.com/influxdb3/core/api/authentication/) | `--without-auth`, `influxdb3 create token --admin`, `Authorization: Bearer` | 2026-09 |
| 11 | [Grafana — InfluxDB query editor](https://grafana.com/docs/grafana/latest/datasources/influxdb/query-editor/), [Configure the InfluxDB data source](https://grafana.com/docs/grafana/latest/datasources/influxdb/configure/) | SQL макро `$__timeFilter`, `$__dateBin`; SQL нь Flight SQL (gRPC), TLS-гүй үед Insecure Connection | 2026-09 |
| 12 | [InfluxDB 3 Core — Use Grafana](https://docs.influxdata.com/influxdb3/core/visualize-data/grafana/) | InfluxDB эх сурвалжийн SQL тохиргоо (database, token, insecure) | 2026-09 |
| 13 | [Node-RED — Importing and Exporting Flows](https://nodered.org/docs/user-guide/editor/workspace/import-export) | Import цонх, `Ctrl-I` | 2026-09 |
| 14 | [Node-RED — Running under Docker](https://nodered.org/docs/getting-started/docker) | `/data` хэрэглэгчийн хавтас, volume | 2026-09 |
| 15 | [Node-RED — Handling errors](https://nodered.org/docs/user-guide/handling-errors) | Catch зангилаа ба `node.error` | 2026-09 |
| 16 | [iptables(8)](https://man7.org/linux/man-pages/man8/iptables.8.html), [nft(8)](https://www.netfilter.org/projects/nftables/manpage.html) | `-I`/`-D`/`-S`; `add table/chain … hook output`, `delete table` | 2026-09 |
| 17 | [mount(8)](https://man7.org/linux/man-pages/man8/mount.8.html), [fallocate(1)](https://man7.org/linux/man-pages/man1/fallocate.1.html) | `mount -o loop` файлаас loop төхөөрөмж үүсгэх; файлд зай урьдчилан хуваарилах | 2026-09 |
