# Лаб 1 — Хоёр давхаргат платформ ба ирмэг–үүлний гүүр

| | |
|---|---|
| **7 хоног** | III |
| **Хугацаа** | 4 цаг |
| **Суралцахуйн үр дүн** | ҮД1 (үүлд суурилсан платформ зохиох), ҮД2 (өргөтгөх боломжтой backend) |
| **Үнэлгээ** | Бичгийн тайлан, 10 оноо |
| **Гол хэмжилт** | Гүүрний RTT, Pi-гийн үлдэгдэл санах ой, үйлчилгээний эхлэх хугацаа |

---

## 1. Зорилго

Энэ лабораторийн эцэст та **хоёр машин дээр тархсан, ажиллагаатай IoT платформ**-той болно. Гол нь стекийг асаах биш — **хаана юу ажиллах ёстойг тоогоор нотлох** явдал.

Гурван асуултад тоон хариулт өгнө:

1. Ирмэгийн давхарга Raspberry Pi 3B дээр **хэдий хэмжээний нөөц** зарцуулах вэ, хэдий хэр илүүдэлтэй вэ?
2. Ирмэг ба үүлний хооронд мессеж явахад **хэдэн миллисекунд** зарцуулагдах вэ?
3. Яагаад платформын давхаргыг (EMQX, InfluxDB, Grafana) Pi 3B дээр ажиллуулах **боломжгүй** вэ — таамаглал биш, тооцоо?

---

## 2. Урьдчилсан нөхцөл

`SETUP.md` бүрэн дуусгасан байх ёстой. Ялангуяа:

- 🥧 `uname -m` → `aarch64`
- 🥧 `free -h` → Swap 2.0Gi, Mem ~925Mi
- 🥧 `vcgencmd get_throttled` → `0x0`
- 💻 Docker Desktop-д ≥ 6 GB
- 💻 LAN IP мэдэгдэж байгаа

```bash
# 🥧 Pi дээр
cd ~/cnc302/edge && make check      # бүгд OK байх ёстой
```

Аль нэг ✘ байвал **энд зогсоод SETUP.md-д буц**. Лабораторийн 4 цагийг орчин тохируулахад зарцуулж болохгүй.

---

## 3. Онолын сануулга

### Edge–Fog–Cloud континуум

IoT лавлах архитектурт өгөгдөл нэг чиглэлд урсдаггүй. Гурван шийдвэрийн цэг байна:

| Асуулт | Ирмэг дээр | Үүл дээр |
|---|---|---|
| Хэдэн мс дотор хариу хэрэгтэй вэ | < 100 мс | > 1 сек болно |
| Холбоос тасарвал ажиллах ёстой юу | тийм | үгүй |
| Хэдий хэмжээний өгөгдөл боловсруулах вэ | багахан | асар их |
| Түүх хадгалах уу | үгүй (эсвэл түр) | тийм |

Энэ курсын байрлуулалт яг үүнийг дагана: **хурдан, локал, тасалдалд тэсвэртэй зүйл Pi дээр; хүнд, түүхэн, харьцуулсан зүйл компьютер дээр.**

![Зураг 1.1 — Хоёр давхаргат архитектур: зөөврийн компьютер (үүл) ба Raspberry Pi 3B (ирмэг), хооронд нь MQTT гүүр](../docs/img/fig-architecture.svg)

### Гүүр (bridge) гэж юу вэ

MQTT гүүр бол **брокер хоорондын клиент холболт**. Ирмэгийн mosquitto нь үүлний EMQX-д ердийн MQTT клиент шиг холбогдож, тодорхой сэдвийн мессежийг дамжуулна.

```
төхөөрөмж ──► mosquitto (Pi) ══гүүр══► EMQX (компьютер) ──► InfluxDB
                    │
                    └── диск: холбоос тасрахад мессежийг ХАДГАЛНА
```

Гүүрний гурван чухал тохиргоо (`edge/mosquitto/conf.d/bridge.conf`):

| Тохиргоо | Утга | Яагаад |
|---|---|---|
| `topic cnc302/shutis/# out 1` | юуг, хаашаа, QoS хэдээр | угтвар зөрвөл мессеж **хэзээ ч** үүлэнд хүрэхгүй |
| `cleansession false` | session хадгална | тасрахад дараалал үлдэнэ |
| `restart_timeout 5 60` | дахин холбогдох завсарлага | 5→60 сек өсөх backoff |

### Санах ойн хязгаар бол архитектурын хязгаар

ThingsBoard-ын албан ёсны суулгах зааварт хөгжүүлэлт/PoC-д хүртэл **4 GB RAM**-ыг доод шаардлага гэж заасан; манай `stack/docker-compose.tb.yml`-д зөвхөн JVM-д `-Xmx1500m` өгсөн. Raspberry Pi 3B-д **нийт** 1 GB RAM бий (албан ёсны үзүүлэлт), үйлдлийн системд ~925 MiB харагдана. Энэ бол тохиргооны асуудал биш — **физик хязгаар**. Тиймээс платформын давхарга компьютер дээр байх нь тохиромжийн асуудал биш, зайлшгүй шаардлага.

---

## 4. Алхмууд

### Алхам 1 — Ирмэгийн суурь хэмжилт (25 мин) 🥧

Юу ч асаахаас өмнө **хоосон Pi-гийн төлөвийг** бичиж авна. Дараагийн бүх тоо үүнтэй харьцуулагдана.

```bash
cd ~/cnc302
pkill -f vscode-server           # VS Code сервер 150–250 MiB иднэ!
sleep 3
./tools/measure_stack.sh --role edge
```

Гаралтаас дараах хүснэгтийг бөглө:

#### Хүснэгт 1.1 — Pi 3B-гийн суурь төлөв (юу ч ажиллаагүй)

| Хэмжигдэхүүн | Утга | Тэмдэглэл |
|---|---|---|
| Pi загвар | | `Raspberry Pi 3 Model B …` |
| `MemTotal` (MiB) | | ~925 хүлээгдэнэ |
| `MemAvailable` (MiB) | | |
| Swap ашигласан (MiB) | | 0 байх ёстой |
| CPU температур (°C) | | |
| `get_throttled` | | **0x0** байх ёстой |
| microSD чөлөөтэй (GB) | | |
| Ачаалал (1 мин) | | |

> **`gpu_mem` шалгалт:** `vcgencmd get_mem gpu`-ийн утгыг (GPU-д хуваарилсан санах ой) хүснэгтэд бич. SETUP.md Б.3 хийсэн бол `16M` гарна. Албан ёсны баримтаар 1 GB-тай загварт `gpu_mem`-ийн анхдагч утга нь `76`. Гэхдээ Raspberry Pi-гийн баримт `gpu_mem`-ийг «legacy» тохиргоонд ангилж, *Bookworm болон түүнээс хойшхи Raspberry Pi OS дээр албан ёсоор дэмжигдэхгүй* гэж тэмдэглэсэн. Тиймээс хэдэн MiB «хэмнэснийг» таамаглах биш, `MemTotal`-ийг өөрчлөхийн өмнөх ба дараах утгатай харьцуулж **хэмжинэ**.
>
> Албан ёсны баримт: [vcgencmd — get_mem, get_throttled](https://www.raspberrypi.com/documentation/computers/os.html#vcgencmd) · [Legacy config.txt — gpu_mem](https://www.raspberrypi.com/documentation/computers/legacy_config_txt.html#gpu_mem)

---

### Алхам 2 — Үүлний давхаргыг асаах ба хэмжих (35 мин) 💻

```bash
cd ~/cnc302/stack
docker compose --profile core down 2>/dev/null
../tools/measure_stack.sh --role cloud --startup
```

`--startup` нь `docker compose --profile core up -d` ажиллуулж, үйлчилгээ бүрийн **эрүүл болох хүртэлх** хугацааг хэмжинэ. `profiles` шинж өгсөн үйлчилгээ зөвхөн тухайн профайлыг `--profile`-оор идэвхжүүлсэн үед асна.

> Албан ёсны баримт: [Using profiles with Compose](https://docs.docker.com/compose/how-tos/profiles/)

#### Хүснэгт 1.2 — Үүлний үйлчилгээний эхлэх хугацаа

| Үйлчилгээ | Эхэлсэн (сек) | Эрүүл болсон (сек) | RAM (MiB) | CPU % |
|---|---|---|---|---|
| emqx | | | | |
| influxdb | | | | |
| grafana | | | | |
| registry | | | | |
| **Нийт** | | | | |

Шалгах:
```bash
make health              # бүх мөр 200
docker compose ps
```

Хөтчөөр нээ:

| Үйлчилгээ | Хаяг | Нэвтрэх |
|---|---|---|
| EMQX самбар (dashboard) | http://localhost:18083 | admin / `.env`-ийн `EMQX_DASHBOARD_PASSWORD` |
| Grafana | http://localhost:3000 | admin / `.env`-ийн нууц үг |
| InfluxDB | http://localhost:8181/health | — |
| Бүртгэл | http://localhost:8090/health | — |

---

### Алхам 3 — Ирмэгийн давхаргыг асаах (25 мин) 🥧

```bash
cd ~/cnc302/edge
cat .env | grep CLOUD_HOST       # компьютерийн LAN IP мөн үү?
make bridge
make up
```

Гүүр холбогдсоныг **хоёр талаас** батал:

```bash
# 🥧 Pi дээр
make link
# → cnc302/shutis/mhts/lab/pi3b-01/bridge/state 1
```

```bash
# 💻 компьютер дээр
mosquitto_sub -h localhost -t 'cnc302/#' -v
```

`1` гарахгүй бол `docs/troubleshooting.md` §1.

Одоо ирмэгийн агентыг ажиллуул (🥧 өөр терминал):
```bash
cd ~/cnc302/edge && make agent
```

Компьютер дээрх `mosquitto_sub` цонхонд телеметр урсаж эхлэх ёстой. **Хэрэв урсахгүй бол `docs/troubleshooting.md` §2 — сэдвийн угтвар.**

#### Хүснэгт 1.3 — Ирмэгийн үйлчилгээний нөөц

| Хэсэг | RAM (MiB) | CPU % | Тэмдэглэл |
|---|---|---|---|
| mosquitto | | | |
| ирмэгийн агент | | | |
| Docker демон | | | |
| **Нийт нэмэгдсэн** | | | Хүснэгт 1.1-тэй харьцуул |
| **Үлдэгдэл `MemAvailable`** | | | |

---

### Алхам 4 — Гүүрний саатлыг хэмжих (40 мин) 🥧💻

Гурван замын саатлыг харьцуулна. Энэ бол Лаб 3-ын бүрэн хэмжилтийн **урьдчилсан хувилбар**.

![Зураг 1.2 — Саатлын гурван зам: loopback, LAN, гүүр](../docs/img/fig-three-paths.svg)

`qos_latency.py` нь нийтлэгч ба захиалагчийг **нэг процесс** дотор ажиллуулдаг тул хоёр машины цагийн зөрүү (clock skew) хэмжилтэд орохгүй.

**А. Loopback (сүлжээгүй)** — 🥧 Pi дээр, Pi-гийн өөрийн брокер руу:
```bash
cd ~/cnc302
export CLOUD_HOST=$(grep '^CLOUD_HOST=' edge/.env | cut -d= -f2)   # Б, В-д хэрэгтэй
python3 tools/qos_latency.py --host localhost --port 1883 \
        --path loopback --qos 1 --count 300 --interval 0.05
```

**Б. LAN (шууд үүл рүү, гүүрийг тойрч)** — 🥧 Pi дээр:
```bash
python3 tools/qos_latency.py --host $CLOUD_HOST --port 1883 \
        --path lan --qos 1 --count 300 --interval 0.05
```

**В. Гүүрээр** — 🥧 Pi дээр. Нийтлэгч Pi-гийн mosquitto руу бичнэ, мессеж гүүрээр EMQX-д очно, захиалагч EMQX-ээс уншина. Сэдэв нь гүүрийн `topic cnc302/shutis/# out 1` дүрэмд **заавал** багтах ёстой — эс бөгөөс мессеж Pi-гаас гарахгүй:
```bash
python3 tools/qos_latency.py --host localhost --port 1883 \
        --sub-host $CLOUD_HOST --sub-port 1883 \
        --topic cnc302/shutis/mhts/lab/pi3b-01/bench \
        --path bridge --qos 1 --count 300 --interval 0.05
```

> Санамж: `--sub-host`-гүйгээр `--host localhost` гэж ажиллуулбал нийтлэгч, захиалагч хоёулаа Pi-гийн брокерт холбогдоно — энэ нь гүүр биш, loopback-ийг дахин хэмжинэ.

#### Хүснэгт 1.4 — Гурван замын саатал (QoS 1, 300 мессеж)

| Зам | p50 (мс) | p95 (мс) | **p99 (мс)** | max (мс) | Алдагдал % |
|---|---|---|---|---|---|
| loopback (Pi доторх) | | | | | |
| LAN (Pi → EMQX) | | | | | |
| гүүрээр | | | | | |

> **p99 нь гол тоо, дундаж биш.** Pi 3B-гийн Ethernet нь 100 Mb/s (албан ёсны үзүүлэлт), CPU нь 1.2 GHz-ийн 4 цөмт Cortex-A53. Ийм хязгаартай төхөөрөмж дээр p50 сайхан харагдаж байхад саатлын сүүл (p99) хэд дахин том гарч болно. Хэрэглэгчийн мэдэрдэг зүйл нь p99.

---

### Алхам 5 — Нөөцийн хязгаарыг ил гаргах (30 мин) 🥧

Виртуал флотыг Pi-гийн брокер руу чиглүүлж, санах ой хаана ханахыг **бодитоор** үзнэ.

```bash
# 💻 компьютер дээрээс Pi-гийн брокер руу флот илгээнэ
python3 tools/sim_device.py --host <PI-IP> --port 1883 \
        --target edge --devices 50 --interval 1.0

# 🥧 зэрэгцүүлэн хэмжинэ
./tools/measure_stack.sh --role edge --watch 120 5
```

Төхөөрөмжийн тоог 50 → 100 → 200 болгож давтана. Аль үед `MemAvailable` 150 MiB-аас доош унах вэ?

#### Хүснэгт 1.5 — Ирмэгийн ачааллын хариу үйлдэл

| Виртуал төхөөрөмж | mosquitto RAM (MiB) | `MemAvailable` (MiB) | Swap `si/so` | Темп (°C) | `get_throttled` |
|---|---|---|---|---|---|
| 0 (суурь) | | | | | |
| 50 | | | | | |
| 100 | | | | | |
| 200 | | | | | |

> ⚠ Swap идэвхжвэл (`si/so` > 0) **зогсоо**. Тэр бол хязгаар. Цааш шахах нь Pi-г царцаана. Энэ нь алдаа биш, **хэмжилт**.

---

### Алхам 6 — Яагаад платформыг Pi дээр ажиллуулж болохгүй вэ (20 мин)

Таамаглах биш, **тоолох**. 💻 компьютер дээр:

```bash
docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}'
```

> Албан ёсны баримт: [docker container stats](https://docs.docker.com/reference/cli/docker/container/stats/) — `--no-stream` нь нэг удаагийн хэмжилт авна; Linux дээр `MemUsage`-ээс кэшийг хасч тооцдог.

#### Хүснэгт 1.6 — Хэрэв бүгдийг Pi дээр ажиллуулах гэвэл

| Үйлчилгээ | Компьютер дээрх бодит RAM (MiB) | Pi-д багтах уу |
|---|---|---|
| emqx | | |
| influxdb | | |
| grafana | | |
| registry | | |
| **Нийт** | | |
| Pi-д боломжтой (Хүснэгт 1.1) | | |
| **Дутагдал** | | |

Нэмэлт (сонголтот, 💻 хангалттай RAM байвал): ThingsBoard-ыг асааж хэмж.
```bash
docker compose -f docker-compose.yml -f docker-compose.tb.yml \
  --profile core --profile tb up -d
# 2-3 минут хүлээгээд:
docker stats --no-stream cnc302-thingsboard
```
Энэ нэг тоо (1.2–1.8 GiB) нь Pi-гийн **нийт** санах ойноос хэдэн дахин их вэ?

---

### Алхам 7 — Grafana-д амьд самбар (25 мин) 💻

**Анхаар:** Лаб 1-д MQTT-ээс InfluxDB руу бичих шугам хараахан **байхгүй** (Лаб 5-д Node-RED-ээр хийнэ). Тиймээс самбар хоосон байх болно. Доорх түр шугам нь `health` ба `bridge/state` мессежийг InfluxDB 3 Core-ын `/api/v3/write_lp` руу line protocol болгон бичнэ (💻 тусдаа терминал, `jq` шаардлагатай):

```bash
cd ~/cnc302/stack
docker compose exec influxdb influxdb3 create database cnc302   # аль хэдийн байвал алдаа өгнө — зүгээр

mosquitto_sub -h localhost -v \
  -t 'cnc302/shutis/+/+/+/health' -t 'cnc302/shutis/+/+/+/bridge/state' |
while read -r topic payload; do
  dev=$(echo "$topic" | cut -d/ -f5); ch=$(echo "$topic" | cut -d/ -f6)
  if [ "$ch" = health ]; then
    line=$(echo "$payload" | jq -r --arg d "$dev" '"health,device=\($d) " + ([to_entries[]
      | select(.key | IN("cpu_temp_c","cpu_pct","load1","mem_available_mb","swap_used_mb"))
      | select(.value != null) | "\(.key)=\(.value)"] | join(","))')
  else
    line="bridge,device=${dev} state=${payload}i"
  fi
  curl -s -X POST "http://localhost:8181/api/v3/write_lp?db=cnc302" --data-binary "$line"
done
```

> Албан ёсны баримт: [InfluxDB 3 Core — v3 write_lp API](https://docs.influxdata.com/influxdb3/core/write-data/http-api/v3-write-lp/). Line protocol-д `i` дагаваргүй тоо нь float, `1i` нь integer.

1. http://localhost:3000 → **Connections → Data sources** → `InfluxDB3` аль хэдийн бүртгэгдсэн (provisioning, хэл нь SQL, өгөгдлийн сан `cnc302`). **Save & test** дарж шалга.
2. **Dashboards → New → New dashboard** → 3 панел (SQL горим):
   - Pi-гийн CPU температур — Time series:
     `SELECT time, cpu_temp_c FROM health WHERE device = 'pi3b-01' AND $__timeFilter(time) ORDER BY time`
   - `MemAvailable` — Time series:
     `SELECT time, mem_available_mb FROM health WHERE device = 'pi3b-01' AND $__timeFilter(time) ORDER BY time`
   - Гүүрний төлөв — Stat панел:
     `SELECT time, state FROM bridge WHERE device = 'pi3b-01' ORDER BY time DESC LIMIT 1`
3. Хадгална. Дараа нь **Export → Export as JSON** → **Download file**, файлыг `lab01/dashboard.json` нэрээр хадгалж commit хийнэ.

> Албан ёсны баримт: [Grafana 11.6 — Export a dashboard as JSON](https://grafana.com/docs/grafana/v11.6/dashboards/share-dashboards-panels/) · [InfluxDB query editor — SQL macros](https://grafana.com/docs/grafana/v11.6/datasources/influxdb/query-editor/)

> Энэ самбар Лаб 5-д гүүр тасрахыг **нүдээр харах** гол хэрэгсэл болно.

---

### Алхам 8 — Git commit (10 мин)

```bash
cd ~/cnc302
git add stack/ edge/ lab01/
git commit -m "Лаб 1: хоёр давхаргат платформ, гүүр ажиллаж байна"
git tag lab01-done
git push && git push --tags
```

⚠ `.env`, `bridge.conf` **орохгүй** байгааг шалга:
```bash
git status --short
git ls-files | grep -E '\.env$|bridge\.conf$'    # хоосон байх ЁСТОЙ
```

---

## 5. Хяналтын асуултууд

Тайландаа **тоон баримт заавал иш татаж** хариулна.

1. Хүснэгт 1.4-д гурван замын p99 хэд дахин ялгаатай вэ? Ялгааны **гол шалтгаан** юу вэ — сүлжээ, брокерын боловсруулалт, эсвэл дараалал? Хэрхэн ялгаж тогтоох вэ?

2. Хүснэгт 1.5-д хязгаарлагч нөөц юу байв — RAM, CPU, эсвэл сүлжээ? Хариултаа тоогоор нотол. (Санамж: `docker stats`-ын CPU % нь олон цөм ашиглавал 100%-иас давж болно — 4 цөмт машин дээр 400% хүртэл.)

3. Хүснэгт 1.6-гийн дутагдал хэдэн MiB вэ? Хэрэв Pi 3B-д 2 GB RAM байсан бол платформыг түүн дээр ажиллуулах уу? Яагаад тийм / үгүй?

4. `cleansession false`-ийг `true` болговол юу өөрчлөгдөх вэ? Ямар тохиолдолд `true` нь **зөв** сонголт байх вэ?

5. Гүүр нь `cnc302/shutis/#` сэдвийг дамжуулдаг. Хэрэв өөр баг `SITE=shutis` ашиглаад нэг брокерт холбогдвол юу болох вэ? Үүнээс хэрхэн сэргийлэх вэ (хоёр өөр арга нэрлэ)?

6. Pi дээр `vcgencmd get_throttled` нь `0x50000` буцаав. Энэ юу гэсэн үг вэ, өмнөх хэмжилтүүд хүчинтэй юу?

---

## 6. Хүлээлгэн өгөх зүйл

| # | Зүйл | Байрлал |
|---|---|---|
| 1 | Тайлан (Хүснэгт 1.1–1.6 бөглөсөн) | `lab01/report.md` → PDF |
| 2 | Grafana самбарын JSON | `lab01/dashboard.json` |
| 3 | `measure_stack.sh`-ийн түүхий гаралт | `lab01/out/` |
| 4 | Git tag | `lab01-done` |

---

## 7. Үнэлгээний шалгуур (10 оноо)

| Шалгуур | Оноо |
|---|---|
| Хоёр давхарга ажиллаж, гүүр холбогдсон (амьд үзүүлнэ) | 3 |
| Хүснэгт 1.1–1.6 бүрэн, throttling шалгасан | 3 |
| Хязгаарлагч нөөцийг **зөв тогтоож, тоогоор нотолсон** | 2 |
| Git сан цэвэр, нууц файл ороогүй | 1 |
| Grafana самбар ажиллаж байна | 1 |

---

## 8. Түгээмэл алдаа

| Шинж | Шалтгаан | Шийдэл |
|---|---|---|
| `bridge/state 0` | CLOUD_HOST буруу / галт хана | troubleshooting §1 |
| Гүүр холбогдсон ч мессеж алга | `SITE` зөрсөн | troubleshooting §2 |
| Санах ойн тоо хачин | VS Code сервер ажиллаж байна | `pkill -f vscode-server` |
| `docker stats` санах ой хоосон | cgroup идэвхгүй | SETUP.md Б.5 |
| Саатал 10 дахин хэлбэлзэнэ | throttling эсвэл Wi-Fi | `get_throttled`, кабельд шилжих |
| `exec format error` | 32-bit OS | `uname -m` → aarch64 байх ёстой |

---

## 9. Эх сурвалж

| # | Эх сурвалж | Юуг баталгаажуулсан | Хандсан |
|---|---|---|---|
| 1 | [Raspberry Pi hardware — Raspberry Pi 3 Model B](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html) (эх: [github.com/raspberrypi/documentation](https://github.com/raspberrypi/documentation/blob/master/documentation/asciidoc/computers/raspberry-pi/introduction.adoc)) | 1 GB RAM, 100 Mb/s Ethernet, 4 × USB 2.0 | 2026-09 |
| 2 | [Processors — BCM2837](https://www.raspberrypi.com/documentation/computers/processors.html#bcm2837) (эх: [bcm2837.adoc](https://github.com/raspberrypi/documentation/blob/master/documentation/asciidoc/computers/processors/bcm2837.adoc)) | 4 цөмт Cortex-A53 (Armv8), 1.2 GHz | 2026-09 |
| 3 | [vcgencmd](https://www.raspberrypi.com/documentation/computers/os.html#vcgencmd) (эх: [graphics-utilities.adoc](https://github.com/raspberrypi/documentation/blob/master/documentation/asciidoc/computers/os/graphics-utilities.adoc)) | `get_throttled` битүүд (0x1, 0x2, 0x4, 0x8, 0x10000…0x80000), `get_mem gpu` | 2026-09 |
| 4 | [Legacy config.txt options — gpu_mem](https://www.raspberrypi.com/documentation/computers/legacy_config_txt.html) (эх: [legacy_config_txt/memory.adoc](https://github.com/raspberrypi/documentation/blob/master/documentation/asciidoc/computers/legacy_config_txt/memory.adoc)) | 1 GB загварт анхдагч 76, доод утга 16; Bookworm+ дээр албан ёсоор дэмжигдэхгүй | 2026-09 |
| 5 | [Using profiles with Compose](https://docs.docker.com/compose/how-tos/profiles/) | `--profile`, `profiles:` шинж | 2026-09 |
| 6 | [docker container stats](https://docs.docker.com/reference/cli/docker/container/stats/) | `--no-stream`, `--format 'table {{.Name}}\t{{.MemUsage}}'` | 2026-09 |
| 7 | [EMQX 5.8 — Dashboard](https://docs.emqx.com/en/emqx/v5.8/guides/dashboard/introduction.html) | самбарын анхдагч порт 18083 | 2026-09 |
| 8 | [InfluxDB 3 Core — v3 write_lp API](https://docs.influxdata.com/influxdb3/core/write-data/http-api/v3-write-lp/) | `/api/v3/write_lp?db=`, line protocol | 2026-09 |
| 9 | [influxdb3 create database](https://docs.influxdata.com/influxdb3/core/reference/cli/influxdb3/create/database/) | CLI синтакс, анхдагч host `http://127.0.0.1:8181` | 2026-09 |
| 10 | [Grafana 11.6 — Share dashboards and panels](https://grafana.com/docs/grafana/v11.6/dashboards/share-dashboards-panels/) | Export → Export as JSON | 2026-09 |
| 11 | [Grafana 11.6 — InfluxDB query editor](https://grafana.com/docs/grafana/v11.6/datasources/influxdb/query-editor/) | SQL макро `$__timeFilter(time)` | 2026-09 |
| 12 | [ThingsBoard — Install using Docker](https://thingsboard.io/docs/installation/docker/) | Dev/PoC-д доод тал нь 4 GB RAM | 2026-09 |
