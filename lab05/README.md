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

Хоёр дахь хагас — **энэ бол лабораторийн зүрх** — уплинкийг тасалж, юу амьд үлдэхийг тоогоор хэмжинэ. Хоёр тоог гаргана:

- **RPO** (Recovery Point Objective) — хэдэн секундын өгөгдөл **бүрмөсөн алдагдав**
- **MTTR** (Mean Time To Recovery) — шугам бүрэн эдгэрэх хүртэл хэдэн секунд өнгөрөв

Энэ хоёр өөр үзүүлэлт: систем 5 секундын дараа сэргэж болно (сайн MTTR), гэхдээ тэр хугацааны өгөгдөл бүрэн алдагдсан байж болно (муу RPO).

> **⚠ ЭНЭ ЛАБОРАТОРИЙН ХАМГИЙН ЧУХАЛ УРХИ.** Уплинк сэргэхэд гүүр хуримтлагдсан мессежээ **нэг тэсрэлтээр** урсгана. Хэрэв та `mosquitto_sub`-ыг тэр тэсрэлтийн **дараа** асаавал юу ч харагдахгүй — MQTT нь өнгөрсөн мессежийг шинэ захиалагчид дахин илгээхгүй. Тэгээд "store-and-forward ажиллаагүй" гэсэн **буруу дүгнэлт** гарна. Дахин илгээлт болсон эсэхийг **зөвхөн InfluxDB дотор** (эсвэл эхнээс нь ажиллаж байсан тогтвортой session-тэй захиалагчаар) шалгана.

---

## 2. Урьдчилсан нөхцөл

- Лаб 1–4 дууссан, `lab04-done` тэмдэглэгээ тавигдсан
- 💻 `pipeline` профайл нэмж асаана:

```bash
cd ~/cnc302/stack && make up-pipeline && make health
docker compose ps       # nodered "healthy" болтол 40 сек хүлээнэ
```

- 🥧 Pi дээр `sudo` эрх (`uplink-down` нь iptables/nft, `disk` нь mount шаарддаг)
- 🥧 `stress-ng` суусан: `sudo apt install -y stress-ng`
- 🥧 Гүүр ажиллаж байна: `cd ~/cnc302/edge && make link` → `bridge/state 1`
- 🥧 Терминал бүрд: `set -a && source ~/cnc302/edge/.env && set +a`

---

## 3. Онолын сануулга

### Баталгаа нь давхаргуудын үржвэр биш, хамгийн сул холбоосоор тодорхойлогдоно

QoS 2-оор илгээсэн мессеж брокерт баттай хүрнэ. Гэвч брокероос Node-RED, тэндээс InfluxDB руу явах замд MQTT-ийн баталгаа **байхгүй**. Тиймээс "төгсгөл-төгсгөлийн найдвартай байдал" гэдэг нь давхарга бүрийн баталгааны нийлбэр биш — **хамгийн сул холбоос** юм.

### Хаана буферлэгдэх вэ

| Эвдрэл | Хэн буферлэдэг | Хязгаар |
|---|---|---|
| **Уплинк тасарсан** | ирмэгийн mosquitto-гийн гүүрний дараалал | `max_queued_messages`, microSD |
| Ирмэгийн брокер унтарсан | төхөөрөмж өөрөө (кодлогдсон бол) | төхөөрөмжийн RAM |
| Node-RED/InfluxDB унтарсан | Node-RED-ийн dead-letter файл | диск |
| Диск дүүрсэн | **хэн ч үгүй** | — |

### Store-and-forward-ийн гурван тохиргоо

`edge/mosquitto/mosquitto.conf` ба `conf.d/bridge.conf` дахь гурван мөр л энэ бүхнийг тодорхойлно:

| Тохиргоо | Хаана | Үүрэг |
|---|---|---|
| `cleansession false` | bridge.conf | тасрахад гүүрний session ба дараалал **хадгалагдана** |
| `local_cleansession false` | bridge.conf | гүүрний **локал** талын session мөн хадгалагдана |
| `queue_qos0_messages true` | mosquitto.conf (**глобал**) | QoS 0 мессежийг ч дараалалд оруулна |

> **⚠ Тохиргооны урхи:** `bridge_queue_qos0_messages` гэсэн сонголт **байхгүй** — mosquitto үүнийг танихгүй сонголт гэж үзээд **огт эхлэхгүй**. Зөв нэр нь глобал `queue_qos0_messages`. Гүүрний хэсэгт бичих гэж оролдвол `docker compose logs mosquitto` дотор `Unknown configuration variable` гарна.

**Хүлээгдэх зан төлөв:** эдгээр гурав зөв тохируулагдсан үед уплинк унасан хугацаанд нийтэлсэн мессеж **бүгд** дараалалд орж, холбоос сэргэхэд **дараалал нь хадгалагдан** үүл рүү урсана. Гүүр нь `restart_timeout 5 60`-ийн дагуу 5–60 секундын дотор дахин холбогдохыг оролдоно (практикт үүл эргэж ирсний дараах эхний оролдлого ихэвчлэн шууд амжилттай болно).

---

## 4. Алхмууд

### Алхам 1 — InfluxDB бэлтгэх ба бичилтийг гараар шалгах (25 мин) 💻

```bash
curl -s -X POST 'http://localhost:8181/api/v3/configure/database' \
  -H 'Content-Type: application/json' -d '{"db":"cnc302"}'
curl -s 'http://localhost:8181/api/v3/configure/database?format=json' | jq
# Нэг мөр гараар бичиж, буцааж уншина
curl -s -X POST 'http://localhost:8181/api/v3/write_lp?db=cnc302&precision=millisecond' \
  -H 'Content-Type: text/plain' \
  --data-binary "telemetry,site=test,device=test0 temperature=24.5 $(date +%s%3N)"

curl -s -X POST 'http://localhost:8181/api/v3/query_sql' \
  -H 'Content-Type: application/json' \
  -d '{"db":"cnc302","q":"SELECT * FROM telemetry LIMIT 5","format":"json"}' | jq
```

**Бичилтийн саатлыг хэмжинэ** (5 удаа давтаж, `%{time_total}`-ыг тэмдэглэ):

```bash
for i in 1 2 3 4 5; do curl -s -o /dev/null -w '%{time_total}\n' -X POST \
  'http://localhost:8181/api/v3/write_lp?db=cnc302&precision=millisecond' \
  -H 'Content-Type: text/plain' \
  --data-binary "telemetry,site=test,device=test0 temperature=2$i.0 $(date +%s%3N)"; done
```

#### Хүснэгт 5.1 — Бичих давхаргын суурь

| Хэмжигдэхүүн | Утга | Тэмдэглэл |
|---|---|---|
| `write_lp` дундаж хугацаа (мс) | | 5 хэмжилтийн дундаж |
| `write_lp` хамгийн удаан (мс) | | |
| Хариу код (амжилттай бичилт) | | 204 хүлээгдэнэ |
| `query_sql` мөр буцаав уу | | |

> InfluxDB 2.7 нөөц хувилбар дээр ажиллаж байгаа бол `docs/troubleshooting.md` §6-г уншаад цаашид `verify`-д `--influx2` тугийг нэмнэ.

---

### Алхам 2 — Node-RED шугам ба Grafana самбар (45 мин) 💻

**2.1 Импортлох.** Node-RED (`:1880`) → ☰ → **Import** → `lab05/flows/nodered-pipeline.json`-ийн агуулгыг наана → **Deploy**.

```
mqtt in ─▶ задлах + шошго ─┬─▶ line protocol (түүхий) ─┐
                           │                            ├─▶ InfluxDB бичих ─▶ шалгах ─┬─▶ ok
                           └─▶ 60с цонх ─▶ lp (нэгтгэл)┘                              └─▶ dead-letter
```

**2.2 Хоёр зангилааг шалга.** `mqtt-broker` нь `emqx:1883` (compose сүлжээн доторх нэр, `localhost` **биш**), `http request` нь `http://influxdb:8181/api/v3/write_lp?db=cnc302&precision=millisecond`. Захиалж буй сэдэв: `cnc302/+/+/+/+/telemetry`.

**2.3 Өгөгдөл урсгана.** 🥧 Pi дээр агентаа ажиллуулаад (`cd ~/cnc302/edge && make agent`), 💻 дээр флот нэмнэ. Node-RED-ийн debug самбарт 10 секунд тутам `write_ok` өсөх ёстой:

```bash
cd ~/cnc302 && python3 tools/sim_device.py --target cloud --host localhost --devices 10 --interval 1
```

**2.4 Задлах зангилааны гурван үүрэг** (кодыг нээж уншина):

| Үүрэг | Код дотор | Яагаад |
|---|---|---|
| UNS схемийн шалгалт | `if (p.length !== 6)` | буруу нэршилтэй өгөгдөл санд орохгүй |
| Өгөгдлийн чанар | `temperature < -60 \|\| > 150` | эвдэрсэн мэдрэгч нэгтгэлийг сүйтгэнэ |
| Шошго гаргах | `msg.tags = {site, area, line, device}` | InfluxDB-ийн хэмжээсүүд |

**2.5 Чанарын шүүлт ба dead-letter-ыг туршина:**

```bash
# 💻 хүрээнээс гарсан утга — санд ОРОХГҮЙ байх ёстой
mosquitto_pub -h localhost -t 'cnc302/shutis/mhts/lab/dev9999/telemetry' \
  -m '{"ts":'"$(date +%s%3N)"',"temperature":9999,"humidity":50,"vibration_rms":0.3}'
curl -s -X POST 'http://localhost:8181/api/v3/query_sql' -H 'Content-Type: application/json' \
  -d '{"db":"cnc302","q":"SELECT count(*) c FROM telemetry WHERE device='"'"'dev9999'"'"'","format":"json"}'
docker exec cnc302-nodered wc -l /data/deadletter.jsonl   # dead-letter файлын урт
```

**2.6 Grafana самбар** (`:3000`, эх сурвалж аль хэдийн бүртгэгдсэн). Гурван панель үүсгэж хадгална — Алхам 4-д уплинк тасрахад энэ график дээр **цоорхой** үүсэх ёстой (эсвэл үүсэхгүй; аль нь болохыг та хэмжинэ):

| Панель | Асуулга |
|---|---|
| Температурын цуваа | `SELECT time, temperature, device FROM telemetry WHERE $__timeFilter(time)` |
| Идэвхтэй төхөөрөмж | `SELECT count(DISTINCT device) FROM telemetry WHERE $__timeFilter(time)` |
| Бичилтийн хурд | `SELECT time, count(*) FROM telemetry WHERE $__timeFilter(time) GROUP BY time` |

#### Хүснэгт 5.2 — Шугамын чанарын хяналт

| Хэмжигдэхүүн | Утга |
|---|---|
| `write_ok` (2 минутын дараа) | |
| `write_errors` | |
| Хүрээнээс гарсан утга санд оров уу | |
| `deadletter.jsonl`-ийн мөрийн тоо | |
| Grafana дээр өгөгдөл харагдав уу | |

---

### Алхам 3 — Суурь бүрэн бүтэн байдал: гүүрээр (30 мин) 🥧💻

Эвдрэлгүй үед **алдагдал 0%** байхыг эхлээд батал. Суурь дээр аль хэдийн алдагдаж байвал цааш явах утгагүй.

```bash
# 🥧 терминал 1 — гүүрний төлөвийг бичиж эхэлнэ (ЭНЭ ЦОНХЫГ ЭЦЭС ХҮРТЭЛ БҮҮ ХАА)
cd ~/cnc302 && mkdir -p lab05/out
mosquitto_sub -h localhost -F '{"ts":%U,"state":%p}' \
  -t "cnc302/$SITE/$AREA/$LINE/$DEVICE_ID/bridge/state" > lab05/out/bridge.jsonl

# 🥧 терминал 2 — ирмэгийн брокер руу нийтэлнэ, гүүр үүл рүү дамжуулна
cd ~/cnc302
python3 lab05/data_integrity.py publish --via edge --host localhost \
    --rate 10 --seconds 180 --qos 1 --run-id base --outdir lab05/out
# дараа нь шалгана — InfluxDB нь ҮҮЛ дээр байгааг санаарай
python3 lab05/data_integrity.py verify --influx "http://$CLOUD_HOST:8181" \
    --run-id base --outdir lab05/out
```

#### Хүснэгт 5.3 — Суурь (эвдрэлгүй)

| Хэмжигдэхүүн | Утга |
|---|---|
| Илгээсэн (амжилттай) | |
| Санд олдсон | |
| Алдагдал % | 0.0 байх ЁСТОЙ |
| Холболтын тасалдал | |
| Хамгийн урт тасалдал (мессеж / сек) | / |

---

### Алхам 4 — УПЛИНК ТАСРАХ: RPO ба MTTR (60 мин) 🥧💻

**Энэ бол лабораторийн гол хэсэг.** `uplink-down` нь Pi → үүл чиглэлийн 1883 портыг л хаана: ирмэгийн mosquitto ажилласаар, төхөөрөмжүүд Pi руу нийтэлсээр байна. Энэ нь "бүх зүйл унасан" биш, яг **уплинк тасарсан** туршилт.

**4.1 QoS 1, 60 секундын тасалдал.** Гурван терминал зэрэг:

```bash
# 🥧 терминал 1 — bridge.jsonl бичсээр байна (Алхам 3-аас үргэлжилнэ)
# 🥧 терминал 2 — 5 минут нийтэлнэ
cd ~/cnc302
python3 lab05/data_integrity.py publish --via edge --host localhost \
    --rate 10 --seconds 300 --qos 1 --run-id uplink60 --outdir lab05/out
# 🥧 терминал 3 — 60 секундын дараа уплинкийг 60 секунд таслана
sleep 60 && bash lab05/failure_inject.sh uplink-down 60
```

**4.2 Уплинк унах үед 🥧 дээр дараалал өсөж байгааг хар:**

```bash
mosquitto_sub -h localhost -t '$SYS/broker/messages/stored' -C 1
docker stats --no-stream cnc302-mosquitto        # RAM өсөж байна уу
```

> **Урхинд бүү ор.** Уплинк сэргэсний дараа шинэ `mosquitto_sub` асаавал дахин илгээгдсэн мессеж **харагдахгүй** — тэсрэлт аль хэдийн өнгөрсөн байна. Дахин илгээлтийн нотолгоо нь зөвхөн (а) InfluxDB дэх мөрүүд, (б) Алхам 3-аас хойш тасралтгүй ажиллаж байгаа `bridge.jsonl` хоёр.

**4.3 Шалгах — алдагдлыг гүүрний төлөвөөр ХУВААНА:**

```bash
# 🥧 publish дуусмагц (сэргэхийг 30 сек хүлээгээд)
python3 lab05/data_integrity.py verify --influx "http://$CLOUD_HOST:8181" \
    --run-id uplink60 --outdir lab05/out --bridge-log lab05/out/bridge.jsonl
```

Гаралт нь алдагдлыг **гүүр УНАСАН үед илгээсэн** ба **ГҮҮР АЖИЛЛАЖ байхад илгээсэн** гэж хоёр хуваана.

**4.4 QoS 0-оор давт** (шинэ `--run-id`, ижил хэв маяг):

```bash
python3 lab05/data_integrity.py publish --via edge --host localhost \
    --rate 10 --seconds 300 --qos 0 --run-id uplink60q0 --outdir lab05/out
# 60 сек дараа: bash lab05/failure_inject.sh uplink-down 60 ; дараа нь:
python3 lab05/data_integrity.py verify --influx "http://$CLOUD_HOST:8181" \
    --run-id uplink60q0 --outdir lab05/out --bridge-log lab05/out/bridge.jsonl
```

**4.5 Тасалдлыг уртасга:** ижил туршилтыг `uplink-down 180` (3 минут) -аар давт (`--seconds 420`, `--run-id uplink180`).

#### Хүснэгт 5.4 — Уплинк тасрах: RPO ба MTTR ⭐

| Ажиллалт | QoS | Тасалдал (с) | Илгээсэн | Санд хүрсэн | Алдагдал % | **RPO (с)** | **MTTR (с)** | Гүүр дахин холбогдох хугацаа (с) |
|---|---|---|---|---|---|---|---|---|
| `uplink60` | 1 | 60 | | | | | | |
| `uplink60q0` | 0 | 60 | | | | | | |
| `uplink180` | 1 | 180 | | | | | | |

- **RPO** = хамгийн урт тасалдлын хугацаа (`verify`-ийн "Хамгийн урт тасалдал ... секунд"). Алдагдал 0 бол RPO = 0.
- **MTTR** = уплинк сэргэснээс хойш сүүлчийн хоцорсон мессеж санд бичигдэх хүртэлх хугацаа (`bridge.jsonl`-ийн `state=1` цаг ба InfluxDB дэх сүүлийн `seq`-ийн бичигдсэн цагийг харьцуул).

#### Хүснэгт 5.5 — Гүүрний төлөвөөр хуваасан алдагдал (`--bridge-log`)

| Ажиллалт | Гүүр унасан удаа | Нийт унасан (с) | Гүүр УНАСАН үед: илгээсэн / алдагдсан / % | Гүүр АЖИЛЛАЖ байхад: илгээсэн / алдагдсан / % |
|---|---|---|---|---|
| `uplink60` (QoS 1) | | | / / | / / |
| `uplink60q0` (QoS 0) | | | / / | / / |
| `uplink180` (QoS 1) | | | / / | / / |

> **Хүлээгдэх үр дүн:** `cleansession false` + `local_cleansession false` + `queue_qos0_messages true` тохиргоотой үед **гүүр унасан үед илгээсэн мессеж бүгд** сэргэсний дараа хүрч, **дараалал нь ч хадгалагдана**. Хэрэв тийм гарвал энэ мөрөнд алдагдал 0% байна. Хэрэв 0% биш бол шалтгааныг Хүснэгт 5.7-оор тайлбарла (дараалал дүүрсэн үү, session цэвэрлэгдсэн үү).

---

### Алхам 5 — `cleansession` ба дарааллын хязгаар (35 мин) 🥧

**5.1 `cleansession true` болгож давт.** Гүүрний тохиргоог **шууд** засаад, Алхам 4.1-ийг `--run-id uplink60clean`-ээр давтана:

```bash
cd ~/cnc302/edge
nano mosquitto/conf.d/bridge.conf     # cleansession false → true
docker compose restart mosquitto      # ⚠ `make restart` БИШ!
docker compose logs --tail=20 mosquitto | grep -i bridge
```

> ⚠ `make restart` нь эхлээд `make bridge`-ийг ажиллуулж `bridge.conf`-ыг **загвараас дахин үүсгэдэг** — гар засвар устана. Тиймээс энд `docker compose restart mosquitto`. Дуусаад `make bridge`-ээр анхны төлөвт буцаана.

**5.2 Дарааллын RAM-ын арифметик.** `mosquitto.conf` дахь `max_queued_messages 100000` юу гэсэн үг вэ — тоол:

```
100 000 мессеж × ______ Б (таны ачаалал) = ______ MiB
Pi-гийн боломжтой RAM (Лаб 4, Хүснэгт 4.1) = ______ MiB
→ Дараалал бүрэн дүүрэхэд Pi амьд үлдэх үү: ______
→ Таны хурдаар (______ мсж/с) дараалал дүүрэхэд ______ секунд шаардагдана
```

**5.3 Дарааллын халилтыг үзэх.** Хязгаарыг зориудаар багасгаж, халихыг ажигла:

```bash
cd ~/cnc302/edge
sed -i 's/^max_queued_messages .*/max_queued_messages 500/' mosquitto/mosquitto.conf
docker compose restart mosquitto
# 🥧 өөр терминалд: 120 сек тасалж, 10 мсж/с илгээнэ → 1200 мессеж > 500 дараалал
cd ~/cnc302
python3 lab05/data_integrity.py publish --via edge --host localhost \
    --rate 10 --seconds 240 --qos 1 --run-id qfull --outdir lab05/out
# 30 сек дараа: bash lab05/failure_inject.sh uplink-down 120 ; дараа нь:
python3 lab05/data_integrity.py verify --influx "http://$CLOUD_HOST:8181" \
    --run-id qfull --outdir lab05/out --bridge-log lab05/out/bridge.jsonl
# Дуусаад БУЦААЖ 100000 болгоод дахин асаана
```

#### Хүснэгт 5.6 — `cleansession` ба дарааллын хязгаарын харьцуулалт

| Тохиргоо | Гүүр унасан үед илгээсэн | Алдагдсан | Алдагдал % | Дараалал хадгалагдав уу |
|---|---|---|---|---|
| `cleansession false`, дараалал 100000 (үндсэн) | | | | |
| `cleansession true`, дараалал 100000 | | | | |
| `cleansession false`, дараалал 500 | | | | |

#### Хүснэгт 5.7 — Дарааллын нөөцийн зардал

| Асуулт | Хариулт |
|---|---|
| Нэг мессежийн бодит хэмжээ (Б) | |
| 100 000 мессежийн RAM (MiB) | |
| Дараалал дүүрэх хугацаа таны хурдаар (с) | |
| Дараалал өсөх үед mosquitto-гийн RAM хэдээр өсөв (MiB) | |
| Дараалал халихад аль мессеж хаягдав (хуучин уу, шинэ үү) | |

**5.4 microSD-гийн бичих саатал.** mosquitto-гийн persistence ба InfluxDB хоёулаа диск рүү бичдэг. Pi-гийн картыг хэмж (4 KiB × 2000 синхрон бичилт):

```bash
dd if=/dev/zero of=~/cnc302/sdtest bs=4k count=2000 oflag=dsync 2>&1 | tail -1
rm ~/cnc302/sdtest && vmstat 1 5      # `wa` = I/O хүлээлт
```

Гарсан тоог `autosave_interval 60`-той холбож тайлбарла: mosquitto яагаад бичилт бүрийг шууд диск рүү буулгадаггүй вэ, энэ нь тасалдал үед юу алдах эрсдэлтэй вэ?

---

### Алхам 6 — Бусад эвдрэлүүд (30 мин) 🥧💻

Тус бүрд `publish` ажиллаж байх зуур эвдрэлийг үүсгэнэ (60 секундын дараа), дараа нь `verify`.

```bash
# 🥧 ирмэгийн брокер өөрөө унана — гүүр биш, БРОКЕР
bash lab05/failure_inject.sh broker 30
# 💻 ҮҮЛ дээр: InfluxDB унана. Брокер, гүүр ажилласаар байна!
bash lab05/failure_inject.sh influx 30
docker exec cnc302-nodered wc -l /data/deadletter.jsonl    # dead-letter ажиллав уу
# 🥧 CPU ханалт (дулааны төсөв ч мөн шалгагдана)
bash lab05/failure_inject.sh cpu 45
# 🥧 АЮУЛГҮЙ дискний туршилт — 512 MiB давталтын файл, бодит microSD хөндөгдөхгүй
bash lab05/failure_inject.sh disk 60
# Эцэст нь БҮГДИЙГ сэргээнэ
bash lab05/failure_inject.sh restore
```

> `influx` горим нь хамгийн заль мэхтэй тохиолдол: **төхөөрөмж юу ч анзаарахгүй**, брокер хүлээж авсаар байна, гүүр ажиллаж байна — гэвч өгөгдөл хаана ч хадгалагдахгүй. Ийм эвдрэлийг зөвхөн Node-RED-ийн `write_errors` тоолуур ба dead-letter файлаас л илрүүлнэ. Grafana дээр график тасарна — гэхдээ хэн нэг нь харж байвал л.

#### Хүснэгт 5.8 — ЭВДРЭЛИЙН МАТРИЦ ⭐

| # | Эвдрэл | Үргэлжлэл (с) | Шинж тэмдэг | Илгээсэн | Санд хүрсэн | Алдагдал % | RPO (с) | MTTR (с) | Автоматаар сэргэв үү |
|---|---|---|---|---|---|---|---|---|---|
| 0 | Суурь (эвдрэлгүй) | — | | | | | | | |
| 1 | `uplink-down`, QoS 1 | 60 | | | | | | | |
| 2 | `uplink-down`, QoS 0 | 60 | | | | | | | |
| 3 | `uplink-down`, QoS 1 | 180 | | | | | | | |
| 4 | `cleansession true` | 60 | | | | | | | |
| 5 | Дараалал 500 (халилт) | 120 | | | | | | | |
| 6 | `broker` (ирмэгийн mosquitto) | 30 | | | | | | | |
| 7 | `influx` (үүлний сан) | 30 | | | | | | | |
| 8 | `cpu` | 45 | | | | | | | |
| 9 | `disk` | 60 | | | | | | | |

---

### Алхам 7 — Дүгнэлт ба commit (15 мин) 🥧💻

Багийн төслийн **найдвартай байдлын паспорт**-ыг бич: ямар RPO, ямар MTTR-ыг зорилт болгох вэ, түүнд хүрэхийн тулд ямар тохиргоо шаардлагатай вэ (`max_queued_messages`, `cleansession`, QoS, диск).

```bash
cd ~/cnc302 && bash lab05/failure_inject.sh restore     # бүх зүйл хэвийн эсэхийг батал
(cd edge && make bridge && docker compose restart mosquitto)   # анхны тохиргоо
git add lab05/
# lab05/out/ нь .gitignore-д — зөвхөн үр дүнгийн JSON-г албадан нэмнэ (лог, jsonl-ыг БИШ)
git add -f lab05/out/*-result.json
git status --short
git commit -m "Лаб 5: өгөгдлийн шугам, уплинк тасрах, RPO/MTTR"
git tag lab05-done && git push && git push --tags
# Нууц файл ороогүйг ЗААВАЛ шалга
git ls-files | grep -E '\.env$|bridge\.conf$|\.key$|\.crt$|devices\.csv'   # хоосон байх ЁСТОЙ
```

---

## 5. Хяналтын асуултууд

1. Хүснэгт 5.5-д QoS 1 үед **гүүр унасан хугацаанд** илгээсэн хэдэн мессежээс хэд нь алдагдав? Хэрэв 0 бол аль гурван тохиргоо үүнийг боломжтой болгов? Хэрэв 0 биш бол аль нь дутуу байв?

2. Хүснэгт 5.4-т QoS 0 ба QoS 1-ийн алдагдал хэдээр зөрөв? `queue_qos0_messages true` байхад ялгаа бага гарсан бол энэ нь юуг харуулж байна вэ?

3. Хүснэгт 5.4-т таны RPO ба MTTR тус бүр хэдэн секунд гарав? Аль нь илүү муу вэ, яагаад? Хэрэв мессеж бүгд хүрсэн ч 40 секунд хоцорч ирсэн бол энэ ямар хэрэглээнд хүлээн зөвшөөрөгдөх, ямарт нь болохгүй вэ?

4. Хүснэгт 5.7-д `max_queued_messages 100000` хэдэн MiB шаардаж байна? Pi 3B-гийн үлдэгдэл RAM (Лаб 4, Хүснэгт 4.1)-тай харьцуулахад энэ аюулгүй тоо мөн үү? Та ямар утга сонгох вэ, яагаад?

5. Дараалал 500 болгосон туршилтад (Хүснэгт 5.6) аль мессежүүд алдагдав — эхнийх нь үү, сүүлийнх нь үү? Энэ нь дарааллын халилтын бодлогын талаар юу хэлж байна вэ, таны хэрэглээнд аль нь дээр вэ?

6. `influx` эвдрэлийн үед төхөөрөмж юу ч анзаарсангүй. Хүснэгт 5.8-ын 7-р мөрөнд хэдэн мессеж алдагдав, dead-letter-т хэдэн мөр орсон бэ? Ийм "чимээгүй" эвдрэлийг хэдэн секундын дотор илрүүлэх систем хэрхэн барих вэ?

7. `dd … oflag=dsync` хэмжилтэд microSD хэдэн MB/с, нэг бичилт дунджаар хэдэн мс байв? Энэ тоо mosquitto-гийн `autosave_interval 60` ба InfluxDB-ийн бичилтэд хэрхэн нөлөөлж байна вэ?

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
| Уплинкийн тасалдлын гурван ажиллалт хийгдэж, Хүснэгт 5.4–5.5 бүрэн | 3 |
| **RPO ба MTTR тоогоор, InfluxDB-ийн нотолгоотойгоор** гаргасан | 2 |
| `cleansession` ба дарааллын хязгаарын харьцуулалт (5.6–5.7) | 2 |
| Эвдрэлийн матриц бүрэн, систем цэвэр сэргээгдсэн | 1 |

**Онцгой оноо (+1):** дахин илгээлтийг тогтвортой session-тэй захиалагчаар (эсвэл өөр аргаар) InfluxDB-ээс гадна бие даан баталсан бол.

---

## 8. Түгээмэл алдаа

| Шинж | Шалтгаан | Шийдэл |
|---|---|---|
| Дахин илгээлт "харагдахгүй" | `mosquitto_sub` тэсрэлтийн ДАРАА асаасан | InfluxDB-ээс шалга (§1-ийн урхи) |
| mosquitto огт эхлэхгүй | `bridge_queue_qos0_messages` гэж бичсэн | глобал `queue_qos0_messages`-ыг ашигла |
| Node-RED 404 буцаана | InfluxDB-д `cnc302` сан үүсээгүй | Алхам 1-ийг давт |
| `write_errors` тасралтгүй өснө | line protocol буруу | debug зангилаагаар `msg.payload`-ыг хар |
| `verify` 0 мөр олно | буруу `--influx` эсвэл `--db` | `SELECT * FROM integrity LIMIT 5` |
| Суурь тестэд аль хэдийн алдагдал | сэдвийн угтвар `SITE`-тай зөрсөн | troubleshooting §2 |
| `uplink-down` → эрхийн алдаа | iptables/nft-д sudo эрх хэрэгтэй | `sudo bash lab05/failure_inject.sh uplink-down 60` |
| `bridge.conf` засвар алга болов | `make restart` загвараас дахин үүсгэсэн | `docker compose restart mosquitto` ашигла |
| `disk` горим `mount` алдаа | sudo эрхгүй эсвэл loop модуль алга | эхлээд `sudo -v` |
| Сэргэсний дараа гүүр удаан холбогдоно | `restart_timeout 5 60` backoff | 60 секунд хүртэл хүлээ, `make link`-ээр хар |
