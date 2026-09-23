# `edge/` — ирмэгийн давхарга (Raspberry Pi 3B)

> ⛔ Энэ фолдерыг **зөөврийн компьютер дээр ажиллуулахгүй**. Компьютерийн хэсэг нь `../stack/`.

Pi 3B (албан ёсны үзүүлэлт): **1 GB RAM**, 4×Cortex-A53 @1.2 GHz, 100 Mb/s Ethernet, 4×USB 2.0, microSD. OS-д хэдэн MiB харагдаж, хэд нь ажилд үлдэхийг Лаб 1-д хэмжинэ (`../docs/resource-budget.md`).

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
| `mosquitto` | Docker | 12–25 MiB | локал брокер + үүл рүү гүүр + дараалал (RAM-д; диск рүү autosave-аар) |
| ирмэгийн агент | venv (Docker биш) | 45–70 MiB | Pi-гийн бодит хэмжүүр + процессын дохио → UNS |
| LiteRT (TFLite) дүгнэлт | агентын дотор | +40–90 MiB | Лаб 6: локал аномали илрүүлэлт |
| K3s **agent** | Лаб 8 | ≈ 268 MiB (K3s-ийн Pi 4B хэмжилт) | server нь зөөврийн компьютер дээрх VM; Pi дээр Docker-ийг **зогсоож** ажиллуулна |

RAM-ын тоо бол **таамаг** — Лаб 1-д өөрсдөө хэмжинэ. Агентыг Docker-т биш **venv-д** ажиллуулж байгаа шалтгаан: Docker демон ба контейнерийн давхаргын зардлыг хэмнэх, мөн кодыг засаад шууд дахин ажиллуулах нь хурдан. Лаб 8-д K3s agent-д оруулахдаа `agent/Dockerfile`-ээр дүрсийг **зөөврийн компьютер дээр** arm64-д барьж, Pi-д хуулна (Dockerfile-ийн толгой хэсэг).

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
    ├── Dockerfile                Лаб 8-д K3s agent-д (компьютер дээр arm64-д барина)
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
| `--detector <model>` | TFLite (LiteRT) загвар (Лаб 6). Байхгүй бол босгын горим |
| `--threads 2` | дүгнэлтийн урсгал. 4×A53-д 4 нь ихэвчлэн 2-оос **удаан** |
| `--filter` | зөвхөн аномали + үе үе хураангуй илгээнэ (өгсөх урсгалыг (uplink) хэмнэнэ) |
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

`MemoryMax=200M` тавьсан — systemd-ийн баримтаар хязгаарт багтахгүй бол тухайн unit дотор OOM killer ажиллана. `.env`-ийг `EnvironmentFile=` уншдаг тул тайлбарыг **тусдаа мөрөнд** бич (мөрийн дундах `#` утгад орно).

---

## Хэмжилтийн өмнө ЗААВАЛ

```bash
pkill -f vscode-server        # VS Code Remote сервер ихээхэн RAM иднэ — хэмжээг Лаб 1-д хэмж
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
| Лаб 8-д `bridge/state` анивчина | Compose-ийн mosquitto K3s-ийн pod-той зэрэг ажиллаж байна (ижил client ID) → `docker compose down` |

Дэлгэрэнгүйг `../docs/troubleshooting.md`-ээс.

---

## Эх сурвалж

| # | Эх сурвалж | Юуг баталгаажуулсан | Хандсан |
|---|---|---|---|
| 1 | [mosquitto.conf(5)](https://mosquitto.org/man/mosquitto-conf-5.html) | Бүх тохиргооны түлхүүр ба хамрах хүрээ (глобал / listener / bridge); `keepalive_interval` (анхдагч 60, доод 5); `notification_topic`-ийн анхдагч `$SYS/broker/connection/<remote_clientid>/state`; persistence нь autosave / зогсоох / SIGUSR1 үед бичигдэнэ | 2026-09 |
| 2 | [Mosquitto ChangeLog](https://mosquitto.org/ChangeLog.txt) | 2.0.20 → 2.0.22 засварууд | 2026-09 |
| 3 | [systemd.exec(5)](https://man7.org/linux/man-pages/man5/systemd.exec.5.html) | `EnvironmentFile=`: зөвхөн мөрийн эхний `#`/`;` тайлбар, мөрийн доторх хоосон зай хадгалагдана | 2026-09 |
| 4 | [systemd.resource-control(5)](https://man7.org/linux/man-pages/man5/systemd.resource-control.5.html) | `MemoryMax=` — хязгаар давбал unit дотор OOM killer; K/M/G утга 1024 суурьтай | 2026-09 |
| 5 | [docker image save](https://docs.docker.com/reference/cli/docker/image/save/), [Multi-platform builds](https://docs.docker.com/build/building/multi-platform/) | `--platform` (API 1.48+), `-o` | 2026-09 |
| 6 | [K3s — Import Images](https://docs.k3s.io/add-ons/import-images) | `/var/lib/rancher/k3s/agent/images/` | 2026-09 |
| 7 | [K3s — Resource Profiling](https://docs.k3s.io/reference/resource-profiling) | K3s agent (Pi 4B) ≈ 268 M | 2026-09 |
| 8 | [Raspberry Pi hardware](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html) ([эх](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/raspberry-pi/introduction.adoc)) | Pi 3B-ийн үзүүлэлт | 2026-09 |
