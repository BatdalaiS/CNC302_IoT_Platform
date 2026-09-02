# `edge/` — ирмэгийн давхарга (Raspberry Pi 3B)

> ⛔ Энэ фолдерыг **зөөврийн компьютер дээр ажиллуулахгүй**. Компьютерийн хэсэг нь `../stack/`.

Pi 3B: **1 GB RAM** (~925 MiB харагдана, ~720–780 MiB ашиглах боломжтой), 4×Cortex-A53 @1.2 GHz, 100 Mbit (USB 2.0-ийн зурвасыг хуваана), microSD.

---

## Хурдан эхлэх

```bash
cp .env.example .env
nano .env            # CLOUD_HOST = зөөврийн компьютерийн LAN IP (localhost БИШ)
make bridge          # .env → mosquitto/conf.d/bridge.conf
make up              # mosquitto асаана
make link            # → bridge/state 1 гарвал холбогдсон
make agent           # ирмэгийн агент (өөр терминалд)
```

---

## Юу энд ажиллах вэ

| Хэсэг | Хэрхэн | RAM | Үүрэг |
|---|---|---|---|
| `mosquitto` | Docker | 12–25 MiB | локал брокер + үүл рүү гүүр + диск дээрх дараалал |
| ирмэгийн агент | venv (Docker биш) | 45–70 MiB | Pi-гийн бодит хэмжүүр + процессын дохио → UNS |
| TFLite дүгнэлт | агентын дотор | +40–90 MiB | Лаб 6: локал аномали илрүүлэлт |
| K3s | Лаб 8 | 250–350 MiB | Docker-ийг **зогсоож** ажиллуулна |

Агентыг Docker-т биш **venv-д** ажиллуулж байгаа шалтгаан: контейнерийн давхарга Pi 3B дээр 60–80 MiB нэмнэ, мөн кодыг засаад шууд дахин ажиллуулах нь илүү хурдан. Лаб 8-д K3s-д оруулахын тулд `agent/Dockerfile`-ээр дүрс барина.

---

## `make` командууд

| Комманд | Үйлдэл |
|---|---|
| `make bridge` | `.env`-ээс `conf.d/bridge.conf` үүсгэнэ (**эхлээд энэ**) |
| `make up` | `bridge` + mosquitto асаана |
| `make link` | гүүрний төлөв сонсоно (1 = холбогдсон) |
| `make agent` | ирмэгийн агент (venv байхгүй бол өөрөө үүсгэнэ) |
| `make mem` | санах ой, throttle, температур, ачаалал |
| `make check` | бэлэн байдлын шалгалт (swap, cgroup, NTP, bridge.conf) |
| `make logs` | mosquitto-гийн лог |
| `make ps` | контейнер + `docker stats` |
| `make down` | зогсоох (өгөгдөл үлдэнэ) |
| `make clean` | зогсоох + volume + `bridge.conf` устгах |

---

## Файлууд

```
edge/
├── docker-compose.yml            mosquitto (+ containerized профайл, Лаб 8)
├── .env / .env.example           CLOUD_HOST, UNS байрлал, агентын тохиргоо
├── Makefile
├── mosquitto/
│   ├── mosquitto.conf            persistence, дараалал, хязгаарлалт
│   └── conf.d/
│       ├── bridge.conf.template  ЗАГВАР (Git-д байна)
│       └── bridge.conf           ҮҮСГЭСЭН (.gitignore-д — IP агуулна)
└── agent/
    ├── edge_agent.py             ирмэгийн агент
    ├── requirements.txt
    ├── Dockerfile                Лаб 8-д K3s-д хэрэгтэй
    └── cnc302-edge-agent.service systemd (тэжээл тасрахад сэргэнэ)
```

---

## `edge_agent.py` — гол сонголтууд

```bash
.venv/bin/python agent/edge_agent.py --help
```

| Тохиргоо | Утга |
|---|---|
| `--dry-run` | брокергүйгээр зөвхөн хэвлэнэ (SETUP-д шалгахад) |
| `--interval 2.0` | телеметрийн үе (сек) |
| `--qos 0\|1\|2` | нийтлэх QoS |
| `--anomaly-rate 0.02` | санамсаргүй аномали оруулах магадлал |
| `--detector <model>` | TFLite загвар (Лаб 6). Байхгүй бол босгын горим |
| `--threads 2` | дүгнэлтийн урсгал. 4×A53-д 4 нь ихэвчлэн 2-оос **удаан** |
| `--filter` | зөвхөн аномали + үе үе хураангуй илгээнэ (уплинк хэмнэнэ) |
| `--health-every 15` | хэдэн мөчлөг тутам эрүүл мэндийн мессеж |

Дохио нь `DEVICE_ID`-аар seed хийгдсэн тул **давтагдана** — нэг Pi үргэлж ижил цуваа өгнө. Лаб 6-д загвар харьцуулахад зайлшгүй.

---

## Байнга ажиллуулах (сонголт)

```bash
sudo cp agent/cnc302-edge-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cnc302-edge-agent
journalctl -u cnc302-edge-agent -f
```

`MemoryMax=200M` тавьсан — агент хэтэрвэл systemd таслана. Pi-г нэг GB-тай гэдгийг мартаж болохгүй.

---

## Хэмжилтийн өмнө ЗААВАЛ

```bash
pkill -f vscode-server        # VS Code Remote сервер 150–250 MiB иднэ
vcgencmd get_throttled        # 0x0 байх ЁСТОЙ
free -m | awk '/Mem:/{print $7 " MiB available"}'
```

`get_throttled` нь `0x0` биш бол тэр хэмжилт **хүчингүй**. Хөргөөд дахин хий.

---

## Түгээмэл алдаа

| Шинж | Шийдэл |
|---|---|
| `bridge/state 0` | `CLOUD_HOST` буруу, эсвэл компьютерийн галт хана (SETUP.md А.6) |
| Гүүр холбогдсон ч мессеж алга | `SITE` нь `.env` ба `bridge.conf`-д зөрсөн → `make bridge && make restart` |
| `.env олдсонгүй` | `cp .env.example .env` |
| `paho-mqtt суулгаагүй` | `make venv` |
| Контейнер дахин дахин эхэлнэ | OOM. `docker inspect … OOMKilled`, `free -m`, swap шалга |
| `exec format error` | 32-bit OS. `uname -m` → `aarch64` байх ёстой |

Дэлгэрэнгүйг `../docs/troubleshooting.md`-ээс.
