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
| `Error: Unknown configuration variable` | Тохиргооны түлхүүр буруу | `make bridge` дахин ажиллуул |
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
| `gpu_mem` 64 хэвээр | SETUP.md Б.3 → 48 MiB чөлөөлнө |
| VS Code сервер ажиллаж байна | `pkill -f vscode-server` |
| Ширээний орчинтой OS суулгасан | Lite (64-bit) дахин суулга |
| Үүлний үйлчилгээг Pi дээр асаах гэсэн | ⛔ Битгий. `stack/` нь **компьютер дээр**. |

---

## 4. `exec format error` эсвэл `no matching manifest`

Pi 3B нь **arm64**. 32-bit OS суулгасан бол олон дүрс байхгүй.

```bash
uname -m          # aarch64 байх ЁСТОЙ. armv7l бол 64-bit OS дахин суулга.
docker manifest inspect eclipse-mosquitto:2.0.20 | grep -A2 arm64
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
| `0x50000` | ӨМНӨ НЬ throttling болсон | хөргөөд дахин асаа, дахин хэмж |
| `0x50005` | ЯГ ОДОО хүчдэл дутуу + throttling | тэжээлээ соль (5 V / 2.5 A) |
| темп > 75 °C | хязгаарт ойрхон | хөргөгч, сэнс тавь |

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

`numpy` барих гэж оролдоод удаж байвал (Pi 3B дээр эх кодоос барих нь 20+ минут):
```bash
.venv/bin/pip install --index-url https://www.piwheels.org/simple numpy
```

---

## 9. Docker Desktop: Ollama эхлэхгүй (Лаб 8)

```bash
docker info --format '{{.MemTotal}}' | awk '{printf "%.1f GB\n", $1/1024/1024/1024}'
```
4 GB-аас бага бол → Settings → Resources → Memory → 6 GB → Apply & Restart.

Хүнд үйлчилгээг зогсооно:
```bash
docker compose stop nodered grafana dex graphql-api
docker compose --profile ai up -d ollama
docker compose exec ollama ollama pull qwen2.5:1.5b
```

---

## 10. K3s pod `Pending` эсвэл `OOMKilled` (Лаб 8)

```bash
kubectl -n cnc302 describe pod <нэр> | tail -25
kubectl top nodes
kubectl top pods -n cnc302
```

| Шалтгаан | Шийдэл |
|---|---|
| Docker зэрэг ажиллаж байна | `sudo systemctl stop docker` |
| traefik/servicelb асаалттай | K3s-ийг `--disable traefik --disable servicelb`-ээр дахин суулга |
| `requests` хэт өндөр | `01-config.yaml`, манифестийн requests-ийг бага болго |
| Дүрс олдохгүй (`ErrImagePull`) | `docker save cnc302/edge-agent:v1 \| sudo k3s ctr images import -` |
| metrics-server байхгүй → HPA `<unknown>` | metrics-server-ийг битгий унтраа |

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
