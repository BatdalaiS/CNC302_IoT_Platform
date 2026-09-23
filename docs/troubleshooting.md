# Түгээмэл алдаа ба шийдэл

Эхлээд үргэлж: 🥧 `cd edge && make check` ба 💻 `cd stack && make health`.

---

## 1. Гүүр (bridge) холбогдохгүй

**Шинж тэмдэг:** `make link` → `bridge/state 0`, эсвэл огт мессеж гарахгүй.

| # | Шалгах | Комманд (🥧 Pi дээр) | Хэвийн бол |
|---|---|---|---|
| 1 | Pi үүлийг харж байна уу | `ping -c3 $CLOUD_HOST` | хариу ирнэ |
| 2 | 1883 порт нээлттэй юу | `nc -vz $CLOUD_HOST 1883` | succeeded |
| 3 | Гүүрний лог | `docker compose logs mosquitto \| tail -20` | "Connecting bridge" |
| 4 | bridge.conf үүссэн үү | `cat mosquitto/conf.d/bridge.conf` | `address <IP>:1883` |

| Алдааны мөр | Шалтгаан | Шийдэл |
|---|---|---|
| `Connection refused` | EMQX асаагүй | 💻 `cd stack && make up` |
| `Broken pipe` дахин дахин | Галт хана хааж байна | 💻 SETUP.md А.6 |
| `No route to host` | Өөр дэд сүлжээ | Хоёуланг нэг свичид кабелиар |
| `Error: Unknown configuration variable` | Тохиргооны түлхүүр буруу (эсвэл глобал түлхүүрийг bridge хэсэгт бичсэн) | `mosquitto.conf(5)`-тай тулга; `make bridge` дахин ажиллуул |
| `address 192.168.1.100:1883` | `.env` засаагүй | `nano .env` → CLOUD_HOST |

> **`localhost` бичих нь хамгийн түгээмэл алдаа.** Pi дээрх `localhost` нь Pi өөрөө. Зөөврийн компьютерийн **LAN IP** хэрэгтэй.

---

## 2. Гүүр холбогдсон ч мессеж үүлэнд хүрэхгүй

Бараг үргэлж **сэдвийн угтвар зөрсөн**. Гүүр зөвхөн `cnc302/<SITE>/#`-ийг дамжуулна.

```bash
# 🥧 Pi дээр — гүүр юуг дамжуулж байна
grep '^topic' edge/mosquitto/conf.d/bridge.conf

# 🥧 агент юу нийтэлж байна
grep -E '^(SITE|AREA|LINE|DEVICE_ID)=' edge/.env

# 🥧 локал брокер дээр бодитоор юу байна
mosquitto_sub -h localhost -t '#' -v -W 5
```

`SITE` хоёр газарт ижил байх ёстой. Өөрчилсөн бол `make bridge && make restart`.

---

## 3. Контейнер OOM болж унана (🥧 Pi)

**Шинж тэмдэг:** контейнер өөрөө дахин эхэлнэ, `docker ps` дээр `Restarting`.

```bash
docker inspect cnc302-mosquitto --format '{{.State.OOMKilled}}'   # true бол OOM
dmesg | grep -i 'killed process' | tail -5
free -m
```

| Шалтгаан | Шийдэл |
|---|---|
| Swap тохируулаагүй | SETUP.md Б.5 |
| `MemTotal` хүлээснээс бага | SETUP.md Б.3 — `gpu_mem`-ийн нөлөөг хэмж (legacy тохиргоо, үр дүн баталгаагүй) |
| VS Code сервер ажиллаж байна | `pkill -f vscode-server` |
| Ширээний орчинтой OS суулгасан | Lite (64-bit) дахин суулга |
| Үүлний үйлчилгээг Pi дээр асаах гэсэн | ⛔ Битгий. `stack/` нь **компьютер дээр**. |

---

## 4. `exec format error` эсвэл `no matching manifest`

Pi 3B нь **arm64**. 32-bit OS суулгасан бол олон дүрс байхгүй.

```bash
uname -m          # aarch64 байх ЁСТОЙ. armv7l бол 64-bit OS дахин суулга.
docker manifest inspect eclipse-mosquitto:2.0.22 | grep -A2 arm64
```

---

## 5. Хэмжилт тогтворгүй, дахин давтагдахгүй

```bash
vcgencmd get_throttled
vcgencmd measure_temp
```

| Утга | Утга нь юу вэ | Үйлдэл |
|---|---|---|
| `0x0` | хэвийн | цааш үргэлжлүүл |
| `0x50000` | ӨМНӨ НЬ хүчдэл дутсан (бит 16) + throttling болсон (бит 18) | тэжээлийг шалга, дахин асаагаад дахин хэмж |
| `0x50005` | ЯГ ОДОО хүчдэл дутуу (бит 0) + throttled (бит 2), өмнө нь ч мөн | тэжээлээ соль (5 V / 2.5 A) |
| `0x40000` / `0x4` | өмнө нь / одоо throttled (хүчдэл биш) | хөргөгч, сэнс тавь |
| темп > 80 °C | албан ёсны баримтаар 80–85 °C-д давтамж буурна | хөргөгч, сэнс тавь |

**Throttling эхэлсэн хэмжилтийг тайланд бичиж болохгүй.** Хаяад дахин хий.

Бусад шалтгаан:
- microSD дүүрсэн: `df -h /` → 90%+ бол лог, дүрс цэвэрлэ (`docker system prune`)
- Цаг синхрончлогдоогүй: `timedatectl status`
- Wi-Fi ашиглаж байна: кабельд шилжүүлээрэй

---

## 6. InfluxDB 3 Core эхлэхгүй / комманд танихгүй

InfluxDB 3-ийн CLI түргэн өөрчлөгддөг. Нөөц хувилбар руу шилжинэ:

```bash
# 💻 компьютер дээр
cd stack
docker compose -f docker-compose.yml -f docker-compose.influx2.yml \
  --profile core up -d
```

InfluxDB 2.7-д API өөр: `/api/v2/write?org=...&bucket=...` ба Flux/InfluxQL. Лаб 5-ын Node-RED урсгал дахь `http request` зангилааны URL-ийг тохируулна.

---

## 7. `make bridge` → `.env олдсонгүй`

```bash
cd edge
cp .env.example .env
nano .env
```

---

## 8. Agent: `paho-mqtt суулгаагүй байна`

```bash
cd edge && make venv        # .venv үүсгэж хамаарлыг суулгана
make agent
```

`numpy` эсвэл `ai-edge-litert`-ийг эх кодоос барих гэж оролдвол (удаан) эсвэл `No matching distribution` гарвал OS 32-бит байна — PyPI дээр хоёулаа зөвхөн `aarch64` wheel-тэй:
```bash
uname -m                      # aarch64 байх ЁСТОЙ
.venv/bin/pip install --upgrade pip
.venv/bin/pip install --only-binary=:all: -r agent/requirements.txt
```

---

## 9. Docker Desktop: Ollama эхлэхгүй (Лаб 8)

```bash
docker info --format '{{.MemTotal}}' | awk '{printf "%.1f GB\n", $1/1024/1024/1024}'
```
4 GB-аас бага бол → Windows + WSL 2: `%UserProfile%\.wslconfig`-д `[wsl2]` / `memory=6GB`, дараа нь `wsl --shutdown`. macOS/Linux/Hyper-V: Settings → Resources → Advanced → Memory limit → 6 GB → Apply & restart (SETUP.md А.2).

Хүнд үйлчилгээг зогсооно:
```bash
docker compose stop nodered grafana dex graphql-api
docker compose --profile ai up -d ollama
docker compose exec ollama ollama pull qwen2.5:1.5b
```

---

## 10. K3s pod `Pending`, `OOMKilled` эсвэл Pi нэгдэхгүй (Лаб 8)

K3s **server** нь зөөврийн компьютер дээрх VM, Pi нь **agent** (`lab08/k3s/README.md`).

```bash
# 🖥️ VM дээр
kubectl get nodes -o wide -L kubernetes.io/arch,cnc302/layer
kubectl -n cnc302 describe pod <нэр> | tail -25
kubectl top nodes
kubectl top pods -n cnc302
# 🥧 Pi дээр
sudo journalctl -u k3s-agent -n 50
```

| Шинж | Шалтгаан | Шийдэл |
|---|---|---|
| Pod `Pending`, `didn't match Pod's node affinity/selector` | Pi-д `cnc302/layer` шошго алга | `kubectl label nodes <pi> cnc302/layer=edge` |
| `edge-agent` эхлэхгүй, Events-д дүрсний алдаа | дүрс Pi-д импортлогдоогүй (`imagePullPolicy: Never`) | компьютер дээр `docker save --platform linux/arm64 -o edge-agent-v1-arm64.tar cnc302/edge-agent:v1` → Pi-гийн `/var/lib/rancher/k3s/agent/images/` руу хуул; `sudo k3s ctr images ls \| grep edge-agent` |
| Pi дээрх pod DNS нэр шийдэж чадахгүй | VM ↔ Pi хооронд **8472/udp** (Flannel VXLAN) хаагдсан | галт ханаар 8472/udp нээ (зөвхөн LAN дотор) |
| `kubectl top nodes` дээр Pi гарахгүй | **10250/tcp** (kubelet) хаагдсан | 10250/tcp нээ |
| VM-ийн INTERNAL-IP `10.0.2.x`, Pi нэгдэхгүй | VM NAT адаптертай | VirtualBox → Adapter 1 = **Bridged**, NAT-ыг хас, K3s-ийг дахин суулга |
| `bridge/state` 0/1 анивчина, EMQX-д ижил client ID | Pi дээр Compose-ийн mosquitto гүүр K3s-ийн pod-той зэрэг ажиллаж байна | 🥧 `cd ~/cnc302/edge && docker compose down` |
| `OOMKilled` | Pi-д бодит сул RAM дууссан (reserved алга тул товлогч мэдэхгүй) | хувийн тоог бууруул; Docker-ийг зогсоо (`sudo systemctl stop docker.socket docker`) |
| traefik/servicelb-ийг унтраах гэж "дахин суулгах" | Энэ бол **server VM**-ийн тохиргоо, Pi биш | Pi дээр юу ч хийхгүй — `lab08/k3s/README.md` |
| metrics-server байхгүй → HPA `<unknown>` | metrics-server унтарсан | metrics-server-ийг битгий унтраа |

---

## 11. Git: Pi ба компьютер дээрх хувилбар зөрөв

Кодыг Pi дээр шууд засаад мартах нь энэ курсын хамгийн түгээмэл алдагдсан ажил.

```bash
# 🥧 Pi дээр
git status --short          # засвар байвал commit хийж push хийнэ
git add -A && git commit -m "Лаб N: Pi дээрх засвар" && git push

# 💻 компьютер дээр
git pull --rebase
```

**Зөвлөмж:** VS Code Remote-SSH ашиглавал нэг л хуулбар дээр ажиллана — энэ асуудал үүсэхгүй.

---

## 12. Нууц мэдээлэл Git-д орчихвол

```bash
git rm --cached stack/.env edge/mosquitto/conf.d/bridge.conf lab02/out/devices.csv
git commit -m "Нууц файлыг устгав"
```

⚠ Түүхэнд үлдсэн хэвээр. **Нууц үг, түлхүүрийг бүгдийг нь солино.** Push хийсэн бол `git filter-repo` шаардлагатай — багшид хандана.
