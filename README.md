# CNC302 — Юмсын интернэтийн платформ ба хэрэглээ
## Лабораторийн ажлын сан · Raspberry Pi 3B хувилбар

Энэ сан нь CNC302 хичээлийн **найман лабораторийн ажлыг** агуулна. Найман лаборатори нь тус тусдаа биш — **нэг ажиллаж буй платформыг үе шаттай өргөтгөж бүтээнэ**. Лаборатори бүрийн эцэст таны систем ажиллагаатай хэвээр байх ёстой бөгөөд дараагийн лаборатори үүн дээр үргэлжилнэ.

---

## 1. Хоёр давхаргат ажлын орчин

Энэ курсын гол архитектурын шийдэл: **үүл ба ирмэгийг ХОЁР ӨӨР ТӨХӨӨРӨМЖ дээр** ажиллуулна.

![Зураг 0.1 — Хоёр давхаргат архитектур: зөөврийн компьютер (үүл) ба Raspberry Pi 3B (ирмэг), хооронд нь MQTT гүүр](docs/img/fig-architecture.svg)

| Төхөөрөмж | Үүрэг | Юу ажиллах |
|---|---|---|
| **Оюутны зөөврийн компьютер** | **Үүлний давхарга** (IoT лавлах архитектурын 3-р давхарга) | EMQX, InfluxDB, Grafana, төхөөрөмжийн бүртгэл, Node-RED, GraphQL API, Dex, Ollama |
| **Raspberry Pi 3B** | **Ирмэгийн давхарга** (2–3-р давхаргын зааг) | Mosquitto брокер + үүл рүү гүүр, ирмэгийн агент, LiteRT (TFLite) дүгнэлт, Лаб 8-д K3s agent (server нь зөөврийн компьютер дээрх VM) |

### Яагаад хуваасан бэ

Raspberry Pi 3B-ийн албан ёсны техникийн үзүүлэлт ба үр дагавар:

| Үзүүлэлт | Утга | Үр дагавар |
|---|---|---|
| Санах ой | **1 GB** (OS-д харагдах `MemTotal`-ийг Лаб 1-д хэмжинэ) | ThingsBoard-ын албан ёсны заавар хөгжүүлэлтэд ч 4 GB RAM шаарддаг — огт багтахгүй |
| Процессор | BCM2837, 4 × Cortex-A53 (Armv8) @ 1.2 GHz | JVM-т суурилсан платформ хэт удаан |
| Сүлжээ | **100 Mb/s** Ethernet; 4 × USB 2.0 | Өгсөх урсгал (uplink) 100 Mb/s-ээр хязгаарлагдана |
| Диск | **зөвхөн microSD** | persistence, swap бичилт удаан (Лаб 5-д хэмжинэ) |
| Өргөтгөл | **PCIe байхгүй** | Raspberry Pi AI Kit (Hailo) нь Raspberry Pi 5-д зориулагдсан — боломжгүй |

Гэхдээ энэ бол зөвхөн хязгаарлалт биш. Бодит үйлдвэрлэлийн IoT систем яг **ийм** байдаг: хүчирхэг үүл, сул ирмэг, хооронд нь найдваргүй холбоос. Pi 5 дээр бүгдийг нэг дор ажиллуулах нь илүү тохилог боловч **Edge–Fog–Cloud континуумыг заахгүй**. Pi 3B үүнийг заахаас өөр аргагүй болгоно:

- Гүүр (bridge) яагаад хэрэгтэйг **холбоос тасарч үзсний дараа** ойлгоно (Лаб 5)
- Ирмэг дээрх дүгнэлт яагаад хэрэгтэйг **өгсөх урсгалыг (uplink) хэмнэж үзсний дараа** ойлгоно (Лаб 6)
- Санах ойн төсөв яагаад чухлыг **OOM-той тулгарсны дараа** ойлгоно (Лаб 1)

> **Зарчим:** Хүнд зүйл **үүл** дээр, хурдан хариу шаардсан зүйл **ирмэг** дээр. Аль ч алхмыг эхлэхийн өмнө "энэ хаана ажиллах ёстой вэ?" гэж асуу. Заавар бүрийн алхам бүрд 💻 (зөөврийн компьютер) эсвэл 🥧 (Pi) тэмдэглэгээ байна.

---

## 2. Сангийн бүтэц

```
CNC302-labs/
├── README.md              ← энэ файл
├── SETUP.md               ← Лаб 1-ээс өмнө нэг удаа хийх бэлтгэл
│
├── stack/                 💻 ҮҮЛ — зөөврийн компьютер дээр
│   ├── docker-compose.yml       ← ГОЛ АЖЛЫН ФАЙЛ, лаборатори бүрт өснө
│   ├── docker-compose.tb.yml    ← ThingsBoard (сонголтот харьцуулалт)
│   ├── docker-compose.influx2.yml  ← InfluxDB 2.7 нөөц хувилбар
│   ├── .env.example
│   └── Makefile
│
├── edge/                  🥧 ИРМЭГ — Raspberry Pi 3B дээр
│   ├── docker-compose.yml       ← mosquitto
│   ├── mosquitto/
│   │   ├── mosquitto.conf
│   │   └── conf.d/bridge.conf.template   ← `make bridge` үүсгэнэ
│   ├── agent/
│   │   ├── edge_agent.py        ← ирмэгийн агент
│   │   ├── Dockerfile           ← Лаб 8-д K3s agent-д (компьютер дээр arm64-д барина)
│   │   └── cnc302-edge-agent.service
│   ├── .env.example
│   └── Makefile
│
├── tools/                 бүх лабораторид хэрэглэгдэх хэрэгслүүд
│   ├── sim_device.py            ← виртуал төхөөрөмжийн флот
│   ├── qos_latency.py           ← QoS × зам (loopback/LAN/bridge) саатал
│   └── measure_stack.sh         ← --role edge|cloud
│
├── lab01/ … lab08/        лаборатори бүрийн заавар ба ажлын файлууд
│   ├── README.md                ← ЗААВАР
│   ├── *.py *.sh
│   └── out/                     ← гаралт (.gitignore-д)
│
└── docs/
    ├── report-template.md
    ├── troubleshooting.md
    └── resource-budget.md       ← 1 GB-ын арифметик
```

### `stack/` ба `edge/` фолдерын дүрэм

`stack/docker-compose.yml` болон `edge/docker-compose.yml` бол **таны багийн гол ажлын файлууд**. Лаборатори бүрт та тэдгээр рүү үйлчилгээ нэмж, тохиргоо өөрчилнө. Эвдэрсэн бол Git-ийн түүхээс сэргээнэ:

```bash
git log --oneline -- stack/docker-compose.yml
git checkout <commit> -- stack/docker-compose.yml
```

Тиймээс **лаборатори бүрийн эцэст commit хийх** нь зөвхөн үнэлгээний шаардлага биш, өөрийн даатгал юм.

---

## 3. Compose профайл (юуг хаана ажиллуулах)

### 💻 Үүл — `stack/`

| Профайл | Үйлчилгээ | Хэзээ | RAM |
|---|---|---|---|
| `core` | emqx, influxdb, grafana, registry | Лаб 1-ээс эхлэн үргэлж | ~1.2 GB |
| `pipeline` | + nodered | Лаб 5-аас | +0.2 GB |
| `app` | + dex, graphql-api | Лаб 7-оос | +0.2 GB |
| `ai` | + ollama | Лаб 8 | +2–3 GB |
| `tb` | + thingsboard (хуучин `tb-postgres` загвар) | Лаб 2, зөвхөн харьцуулалт | +2 GB (албан ёсоор ≥ 4 GB) |

```bash
cd stack
make up              # core
make up-pipeline     # + Node-RED
make up-app          # + Dex, GraphQL
make up-ai           # + Ollama
```

**Docker Desktop-ийн санах ой:** анхдагчаар хостын санах ойн 50%. **6 GB** өгнө: Windows-ийн WSL 2 backend дээр `%UserProfile%\.wslconfig`-ийн `[wsl2] memory=6GB`-ээр, macOS/Linux дээр Settings → Resources → Advanced → Memory limit-ээр (SETUP.md А.2). Лаб 8-д Ollama-д үүнээс бага бол ажиллахгүй. Лаб 8-д нэмээд K3s server VM (4 GB) хэрэгтэй тул зөөврийн компьютерт **16 GB RAM** тав тухтай.

### 🥧 Ирмэг — `edge/`

```bash
cd edge
cp .env.example .env
nano .env            # CLOUD_HOST = зөөврийн компьютерийн IP
make bridge          # bridge.conf үүсгэнэ
make up              # mosquitto
make agent           # ирмэгийн агент (өөр терминалд)
make link            # гүүр холбогдсон эсэх: 1 = тийм
```

Санах ойн нарийвчилсан төсвийг `docs/resource-budget.md`-ээс үзнэ үү.

---

## 4. Unified Namespace — сэдвийн бүтэц

Бүх лаборатори нэг сэдвийн бүтэц ашиглана. Энэ нь ISA-95 шатлалыг дагана:

```
cnc302/<site>/<area>/<line>/<device>/<channel>
       shutis  mhts   lab    pi3b-01  telemetry
```

| Суваг | Чиглэл | Агуулга |
|---|---|---|
| `telemetry` | ирмэг → үүл | хэмжилтийн өгөгдөл |
| `health` | ирмэг → үүл | Pi-гийн температур, RAM, throttle |
| `status` | ирмэг → үүл | retained: онлайн/офлайн (LWT) |
| `anomaly` | ирмэг → үүл | зөвхөн онцгой тохиолдол |
| `bridge/state` | ирмэг → үүл | 1 = гүүр холбогдсон, 0 = тасарсан |
| `cmd`, `config` | үүл → ирмэг | команд, тохиргоо |
| `ota/…` | хоёр тал | firmware шинэчлэлт (Лаб 2) |

Гүүр нь `cnc302/<site>/#` сэдвийг үүл рүү дамжуулна. **Тиймээс сэдвийн угтвар буруу бол мессеж үүлэнд хэзээ ч хүрэхгүй** — Лаб 1-ийн хамгийн түгээмэл алдаа.

---

## 5. Багийн Git санг эхлүүлэх

```bash
# 1. Энэ санг үлгэр болгон хуулж авах (шууд clone биш — өөрийн түүх хэрэгтэй)
git clone --depth 1 <багшийн-сангийн-хаяг> cnc302-labs-template
cp -r cnc302-labs-template <багийн-нэр>-cnc302
cd <багийн-нэр>-cnc302
rm -rf .git && git init && git add . && git commit -m "Лаб 1: эхлэл"

# 2. Өөрийн алсын санг холбох (GitHub/GitLab, ХУВИЙН сан)
git remote add origin <таны-сангийн-хаяг>
git push -u origin main

# 3. Багшид унших эрх өгөх
```

**Commit хийх дүрэм:** лаборатори бүрийн эцэст `git tag lab01-done` мэтээр тэмдэглэнэ. Багш үнэлгээг эдгээр тэмдэглэгээгээр шалгана.

**Хэзээ ч commit хийхгүй:** `.env`, `bridge.conf` (IP агуулна), нууц үг, хувийн түлхүүр, `*.pem`, сертификат, `devices.csv`, том лог файл. `.gitignore` бэлэн байгаа.

> Pi дээр Git санг **клонлож** ажиллуулна. Кодыг Pi дээр шууд засаж, зөөврийн компьютер дээр мартах нь энэ курсын хамгийн түгээмэл алдагдсан ажил. VS Code Remote-SSH ашиглавал энэ асуудал байхгүй.

---

## 6. Лабораторийн жагсаалт

| № | 7 хоног | Нэр | Гол хэмжилт |
|---|---|---|---|
| 1 | III | Хоёр давхаргат платформ ба гүүр | Гүүрний RTT, Pi-гийн үлдэгдэл RAM, эхлэх хугацаа |
| 2 | V | Төхөөрөмжийн амьдралын мөчлөг ба OTA | Бүртгэлийн хурд, OTA-гийн хугацаа ба амжилтын хувь |
| 3 | VII | MQTT 5.0, UNS ба гурван зам | QoS × зам: p50/p95/**p99** |
| 4 | IX | Багтаамжийн хязгаар: ирмэг ба үүл | Аль нөөц ХАМГИЙН ТҮРҮҮНД ханав |
| 5 | XI | Өгөгдлийн шугам ба холбоос тасрах | Store-and-forward-ийн алдагдал, RPO ба MTTR |
| 6 | XII | Ирмэгийн хиймэл оюун (CPU дээр) | Дүгнэлтийн саатал, RAM, шүүлтийн үр ашиг |
| 7 | XIV | Хэрэглээний давхарга ба Zero Trust | Аюулгүй байдлын 9 шалгалт |
| 8 | XV | Дижитал ихэр, GenAI, ирмэгийн K3s | K3s-ийн санах ойн зардал, шилжүүлэлтийн үр дүн |

---

## 7. Тайлангийн ерөнхий шаардлага

Тайлангийн загвар: `docs/report-template.md` → `labNN/report.md` болгон хуулж бөглөнө (PDF болгон хөрвүүлж өгнө):

1. **Багийн гишүүд ба хувь нэмэр** — хэн юу хийсэн (нэг өгүүлбэрээр)
2. **Гүйцэтгэсэн алхмууд** — товч, дэлгэцийн зураг биш харин **комманд ба гаралт**
3. **Хэмжилтийн хүснэгт** — заавар дахь хоосон хүснэгтийг бөглөсөн байх
4. **Дүгнэлт** — тоон үр дүн юу гэсэн үг вэ, төслийн шийдэлд хэрхэн нөлөөлөх вэ
5. **Тулгарсан асуудал ба шийдсэн арга**
6. **Git commit-ийн хаяг (hash)** — тайланд харгалзах кодын төлөв

> **Хамгийн чухал:** тайлан бол **нотолгоо**, дэлгэцийн зургийн цуглуулга биш. Тоон үр дүнгүй тайлан 50%-иас дээш оноо авахгүй.

Лаб 4 ба Лаб 8-ыг бичгийн тайлангийн оронд **10 минутын багийн үзүүлэн**-ээр үнэлнэ.

---

## 8. Үнэлгээ

Лабораторийн ажил нийт дүнгийн **25%** эзэлнэ (6 тайлан + 2 үзүүлэн). Лаборатори бүр 10 оноо:

| Шалгуур | Оноо |
|---|---|
| Ажиллагаатай үр дүн (систем ажиллаж байна) | 3 |
| Хэмжилт бүрэн, зөв аргачлалаар хийгдсэн | 3 |
| Дүгнэлт үндэслэлтэй, тоон баримтад тулгуурласан | 2 |
| Git сан цэвэр, түүх ойлгомжтой | 1 |
| Тайлангийн чанар, ойлгомжтой байдал | 1 |

Хугацаа хэтэрсэн тайлан өдөр тутам 10% хасагдана.

---

## 9. Хэмжилтийн үнэн зөв байдал — Pi 3B-ийн тусгай санамж

Энэ курс **тоо хэмжилт** дээр тулгуурладаг. Pi 3B дээр гурван зүйл бүх хэмжилтийг гажуудуулна:

1. **Дулааны хязгаарлалт (throttling).** Албан ёсны баримтаар 80–85 °C-д Arm цөмийн давтамж аажмаар буурч, 85 °C-д GPU ч мөн буурна. Идэвхтэй хөргөлт, эсвэл ядаж наалдац бүхий хөргөгч заавал хэрэгтэй. Хэмжилт бүрийн өмнө ба дараа:
   ```bash
   vcgencmd get_throttled     # 0x0 байх ЁСТОЙ
   ```
   `0x0` биш бол тэр хэмжилтийг **хаяж, хөргөөд дахин хий**.

2. **Тэжээл.** Pi 3B-д албан ёсоор 5 V / 2.5 A шаардлагатай. Сул тэжээл бол ачаалал дор хүчдэл унаж (`get_throttled`-ийн бит 0 = undervoltage), throttling эхэлнэ. Утасны цэнэглэгч ихэвчлэн хангалтгүй.

3. **microSD.** Хямд карт дээр mosquitto-гийн persistence ба swap-ын бичилт удаан. A1/A2 ангиллын карт хэрэглэ. Лаб 5-д үүнийг бодитоор хэмжинэ.

`tools/measure_stack.sh --role edge` эдгээрийг автоматаар шалгаж анхааруулна. **Лаборатори бүрийн эхэнд эхлээд үүнийг ажиллуул.**

---

## 10. Анхааруулга — хувилбарын эрсдэл

Энэ сан дахь бүх дүрс (image) тодорхой хувилбарт **бэхлэгдсэн** (pinned). Нээлттэй эхийн төслүүд, ялангуяа **InfluxDB 3 Core** болон **Edge Impulse**-ийн CLI, тохиргоо түргэн өөрчлөгддөг. Лабораториудыг доорх хувилбараар шалгасан (2026-09):

| Дүрс | Хувилбар | Яагаад энэ хувилбар |
|---|---|---|
| `emqx/emqx` | **5.8.6** | Лаб 1–2-т бодитоор туршсан. 5.8 бол LTS салбар (EOL 2027-08-27) бөгөөд **Apache 2.0** лицензтэй. EMQX **5.9.0-ээс эхлэн Business Source License (BSL) 1.1**-д шилжсэн: нэг зангилааг үнэгүй ажиллуулж болох ч кластерт арилжааны лиценз хэрэгтэй (магадлан итгэмжлэгдсэн их сургууль арилжааны бус хэрэглээнд үл хамаарна). Лицензийн файл, нөхцөлийг оюутнуудад тайлбарлах шаардлагагүй байлгахын тулд 5.8.x-д үлдээв. |
| `influxdb` | 3.2-core | Лаб 5, 7-ийн команд энэ хувилбараар шалгагдсан (одоогийн Core 3.11) |
| `grafana/grafana` | 11.6.16 | 11.6.0-ийн аюулгүй байдлын засвар (CVE-2025-4123, CVE-2026-27876) бүхий 11.6 салбар |
| `nodered/node-red` | 4.0.9 | Лаб 5 |
| `dexidp/dex` | v2.41.1 | Лаб 7 |
| `eclipse-mosquitto` | 2.0.22 | 2.0 салбарын сүүлийн дүрс (2.0.21-ийн аюулгүй байдлын засвартай); 2.1 нь зан төлөвийн өөрчлөлттэй |
| `ollama/ollama` | 0.5.13 | Лаб 8 |

**Багшид:** хичээлийн улирал эхлэхээс өмнө нэг Raspberry Pi 3B **ба** нэг зөөврийн компьютер дээр бүх найман лабыг эхнээс нь дуустал ажиллуулж шалгана уу. Хувилбар зөрчилдвөл:

- InfluxDB 3-тэй асуудал гарвал: `docker compose -f docker-compose.yml -f docker-compose.influx2.yml up -d` (InfluxDB 2.7 нөөц хувилбар)
- Дүрсийн arm64 дэмжлэгийг шалгах: `docker manifest inspect <image> | grep arm64`
- Pi 3B бол **arm64 (aarch64)**. 64-bit OS суулгах ёстой — 32-bit дээр зарим дүрс огт байхгүй.

`docs/troubleshooting.md`-д түгээмэл алдаа, шийдлийг цуглуулсан.

---

## Эх сурвалж

| # | Эх сурвалж | Юуг баталгаажуулсан | Хандсан |
|---|---|---|---|
| 1 | [Raspberry Pi hardware](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html) ([эх: GitHub](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/raspberry-pi/introduction.adoc)), [BCM2837](https://www.raspberrypi.com/documentation/computers/processors.html#bcm2837) ([эх](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/processors/bcm2837.adoc)) | Pi 3B: BCM2837, 4×Cortex-A53 @1.2 GHz, 1 GB, 100 Mb/s Ethernet, 4×USB 2.0 | 2026-09 |
| 2 | [Frequency management and thermal control](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#frequency-management-and-thermal-control) ([эх](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/raspberry-pi/frequency-management.adoc)) | 80–85 °C-д Arm цөм, 85 °C-д GPU throttle | 2026-09 |
| 3 | [vcgencmd get_throttled](https://www.raspberrypi.com/documentation/computers/os.html#vcgencmd) ([эх](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/os/graphics-utilities.adoc)) | бит 0 = undervoltage | 2026-09 |
| 4 | [Getting started — power supply](https://www.raspberrypi.com/documentation/computers/getting-started.html) ([эх](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/getting-started/setting-up.adoc)) | Pi 3: 5 V / 2.5 A | 2026-09 |
| 5 | [AI Kit](https://www.raspberrypi.com/documentation/accessories/ai-kit.html) ([эх](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/accessories/ai-kit/about.adoc)) | M.2 HAT+ + Hailo, Raspberry Pi 5-д | 2026-09 |
| 6 | [EMQX Licensing FAQ](https://www.emqx.com/en/content/license-faq), [EMQX — License](https://docs.emqx.com/en/emqx/latest/deploy/license.html) | 5.9.0+ нь BSL 1.1, өмнөх нь Apache 2.0; нэг зангилаа үнэгүй; академийн арилжааны бус хэрэглээ | 2026-09 |
| 7 | [EMQX Version Lifecycle (EOL)](https://docs.emqx.com/en/emqx/latest/changes/eol-ee.html) | 5.8 LTS, EOL 2027-08-27 | 2026-09 |
| 8 | [Grafana security release (CVE-2026-27876, CVE-2026-27880)](https://grafana.com/blog/grafana-security-release-critical-and-high-severity-security-fixes-for-cve-2026-27876-and-cve-2026-27880/), [CVE-2025-4123](https://grafana.com/blog/grafana-security-release-high-severity-security-fix-for-cve-2025-4123/) | 11.6.0 нөлөөлөлд өртсөн; 11.6.14 ба 11.6.1+security-01 засвартай | 2026-09 |
| 9 | [Mosquitto ChangeLog](https://mosquitto.org/ChangeLog.txt) | 2.0.21 аюулгүй байдлын засвар; 2.1.0 зан төлөвийн өөрчлөлт | 2026-09 |
| 10 | [ThingsBoard CE — Docker](https://thingsboard.io/docs/installation/docker/) | Хөгжүүлэлт/PoC-д 1 цөм, 4 GB RAM | 2026-09 |
| 11 | [Docker Desktop — Settings](https://docs.docker.com/desktop/settings-and-maintenance/settings/), [WSL config](https://learn.microsoft.com/en-us/windows/wsl/wsl-config) | Анхдагч 50%; WSL 2-т `.wslconfig` | 2026-09 |
| 12 | [K3s — Requirements](https://docs.k3s.io/installation/requirements) | server 2 GB — Pi 3B-д багтахгүй; agent 512 MB | 2026-09 |
| 13 | Docker Hub (`hub.docker.com/v2/repositories/…/tags`) | Бүх бэхэлсэн tag байгаа ба arm64 хувилбартай | 2026-09 |
