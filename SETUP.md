# SETUP — Лаб 1-ээс өмнө нэг удаа хийх бэлтгэл

Хугацаа: **60–90 минут**. Үүнийг лабораторийн цагаар биш, **I–II долоо хоногийн бие даалтаар** гүйцэтгэнэ. Лаб 1 эхлэхэд энэ бүхэн бэлэн байх ёстой.

Бэлтгэл нь хоёр машин дээр явагдана: **💻 зөөврийн компьютер** (үүл) ба **🥧 Raspberry Pi 3B** (ирмэг). Аль хэсэг хаана хийгдэхийг тэмдэглэгээгээр заасан.

---

## А. 💻 Зөөврийн компьютер дээр

### А.1 Шаардлагатай програм

| Програм | Шалгах комманд | Тайлбар |
|---|---|---|
| Git | `git --version` | 2.30+ |
| Python | `python3 --version` | 3.10+ |
| Docker Desktop | `docker compose version` | v2.20+ |
| VS Code | — | + **Remote - SSH**, **Docker**, **YAML** өргөтгөл |
| SSH клиент | `ssh -V` | Windows 10/11-д суулгаастай |
| MQTT Explorer | — | http://mqtt-explorer.com (сонголт: `mosquitto_sub`) |

### А.2 Docker Desktop-ийн санах ой (ЗААВАЛ)

Анхны тохиргоогоор Docker Desktop-д 2–4 GB л өгдөг. Энэ нь Лаб 8-д Ollama-г ажиллуулахад хүрэлцэхгүй.

**Settings → Resources → Memory → 6 GB** (компьютерт 16 GB байвал 8 GB).

```bash
docker info --format '{{.MemTotal}}' | awk '{printf "Docker-т %.1f GB\n", $1/1024/1024/1024}'
```

4 GB-аас бага бол Лаб 8-д `ai` профайл ажиллахгүй.

### А.3 Python орчин

```bash
cd <багийн-сан>
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r tools/requirements.txt
```

Шалгах:
```bash
python tools/sim_device.py --dry-run --devices 2 --count 3
```
Брокергүйгээр 6 мессежийн JSON хэвлэгдэх ёстой. Хэвлэгдэхгүй бол цааш явахгүй.

### А.4 Үүлний стекийг татаж, асаах

```bash
cd stack
cp .env.example .env
nano .env                          # нууц үгсээ солино
docker compose --profile core pull # 5–10 минут
make up
make health                        # бүгд 200 байх ёстой
```

### А.5 LAN IP хаягаа олох (ЧУХАЛ)

Pi нь зөөврийн компьютерийн **LAN IP**-ээр холбогдоно. `localhost` БИШ.

```bash
cd stack && make ip
# эсвэл Windows дээр:  ipconfig | findstr IPv4
# эсвэл Linux/macOS:   ip -4 addr show scope global | grep inet
```

Гарсан хаягийг (жишээ `192.168.1.57`) тэмдэглэ. Pi-гийн `edge/.env` дотор хэрэгтэй.

> **Wi-Fi-гийн урхи:** зөөврийн компьютер Wi-Fi, Pi кабелиар холбогдсон бол өөр дэд сүлжээнд байж болно. Хамгийн найдвартай нь **хоёуланг нь нэг свич/роутерт кабелиар** холбох.

### А.6 Галт хана (Windows)

Windows Defender анхдагчаар гаднаас ирэх 1883 портыг хаадаг. Pi холбогдож чадахгүй бол:

```powershell
# PowerShell (Administrator)
New-NetFirewallRule -DisplayName "CNC302 MQTT" -Direction Inbound `
  -LocalPort 1883,8181,3000,8090 -Protocol TCP -Action Allow -Profile Private
```

> Зөвхөн **Private** профайлд нээ. Нийтийн сүлжээнд задгай MQTT брокер орхиж болохгүй.

### А.7 SSH түлхүүр үүсгэх

```bash
ssh-keygen -t ed25519 -C "<таны-имэйл>" -f ~/.ssh/cnc302
```

> Нууц түлхүүрийг (`cnc302`) **хэзээ ч** Git санд оруулахгүй.

---

## Б. 🥧 Raspberry Pi 3B дээр

### Б.0 Тоног төхөөрөмжийн шалгуур

| Зүйл | Шаардлага | Яагаад |
|---|---|---|
| Тэжээл | **5 V / 2.5 A** албан ёсны адаптер | Сул тэжээл → хүчдэл унана → throttling → бүх хэмжилт гажина |
| Хөргөлт | Наалдацтай хөргөгч, боломжтой бол сэнс | 4 цөм ачаалалтай ажиллахад 80 °C давна |
| microSD | **A1 эсвэл A2**, 16 GB+ | Хямд карт дээр InfluxDB, persistence бичилт зуун мс саатана |
| Сүлжээ | **Кабель** (Wi-Fi биш) | Pi 3B-ийн Wi-Fi нь 2.4 GHz, лабораторид бөглөрдөг |

### Б.1 Систем суулгах

1. Raspberry Pi Imager → **Raspberry Pi OS Lite (64-bit)**

   > ⚠ **64-bit заавал.** Pi 3B нь arm64 (BCM2837) боловч Imager анхдагчаар 32-bit санал болгодог. 32-bit дээр EMQX, InfluxDB зэрэг олон дүрс огт байхгүй. `Raspberry Pi OS (other)` цэснээс **Lite (64-bit)**-ыг сонгоно.

   > ⚠ **Lite заавал.** Ширээний орчин 250–350 MiB санах ой иднэ. 1 GB-д энэ бол хэт үнэтэй.

2. Imager-ийн тохиргооны цэсэнд (⚙):
   - Хостын нэр: `pi-<багийн-нэр>` (жишээ: `pi-team03`)
   - Хэрэглэгч: `cnc302`, хүчтэй нууц үг
   - SSH идэвхжүүлэх → **Allow public-key authentication only** → А.7-д үүсгэсэн `cnc302.pub`-ийн агуулгыг наах
   - Кабель сүлжээ (Wi-Fi зөвхөн шаардлагатай үед)

### Б.2 Эхний холболт ба шинэчлэл

```bash
ssh -i ~/.ssh/cnc302 cnc302@pi-team03.local

sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git curl jq htop iotop stress-ng mosquitto-clients \
                    python3-venv python3-dev
sudo reboot
```

### Б.3 GPU-гийн санах ойг багасгах (1 GB-ын анхны хэмнэлт)

Ширээний орчингүй Pi-д видео санах ой хэрэггүй. Анхдагч 64 MiB → 16 MiB.

```bash
echo 'gpu_mem=16' | sudo tee -a /boot/firmware/config.txt
```

Энэ нь **48 MiB** чөлөөлнө — Лаб 1-д хэмжинэ.

### Б.4 Docker суулгах

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker                      # эсвэл дахин нэвтэрнэ

docker --version
docker compose version             # v2.20+ байх ёстой
docker run --rm hello-world
```

Docker-ийн лог microSD-г элээхээс сэргийлэх:

```bash
sudo tee /etc/docker/daemon.json > /dev/null <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "5m", "max-file": "2" }
}
EOF
sudo systemctl restart docker
```

### Б.5 Солих файл ба cgroup (ЗААВАЛ)

Анхны тохиргоогоор Pi-гийн swap ердөө 100–200 MiB. 1 GB RAM дээр энэ нь Лаб 4–6-д "container killed (OOM)" алдаа өгнө.

```bash
sudo dphys-swapfile swapoff
sudo sed -i 's/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
free -h                            # Swap: 2.0Gi байх ёстой
```

> **Санамж:** swap нь microSD дээр байгаа тул **маш удаан**. Энэ нь OOM-оос хамгаалах "аюулгүйн сүлжээ" болохоос гүйцэтгэлийн шийдэл биш. Хэрэв Лаб 4-д swap идэвхтэй ажиллаж эхэлбэл (`vmstat 1`-ийн `si/so` багана 0-ээс их) та аль хэдийн хязгаарт хүрсэн — тэр нь хэмжилт өөрөө юм.

cgroup санах ойн хязгаарлалтыг идэвхжүүлэх (`docker stats`-ын тоо зөв гарахад шаардлагатай):

```bash
sudo sed -i '1 s/$/ cgroup_enable=memory cgroup_memory=1/' /boot/firmware/cmdline.txt
sudo reboot
```

Шалгах:
```bash
cat /proc/cgroups | grep memory   # эхний баганад 1 байх ёстой
free -m | head -2                 # Mem нийт ~925 MiB харагдана
```

### Б.6 Цагийн синхрончлол (ЗААВАЛ)

Лаб 3, Лаб 5-ын саатлын хэмжилт цагийн зөрүүнээс шалтгаалж утгагүй болдог. Pi-д бодит цагийн батарей **байхгүй** — асаах бүрд NTP-ээс цагаа авдаг.

```bash
sudo timedatectl set-timezone Asia/Ulaanbaatar
sudo timedatectl set-ntp true
timedatectl status                 # "System clock synchronized: yes"
```

### Б.7 Сангаа Pi дээр байрлуулах

```bash
mkdir -p ~/cnc302 && cd ~/cnc302
git clone <багийн-сангийн-хаяг> .

cd edge
cp .env.example .env
nano .env
#   CLOUD_HOST=192.168.1.57      ← А.5-д олсон IP
#   DEVICE_ID=pi3b-team03        ← баг бүр өөр
make bridge                        # conf.d/bridge.conf үүснэ
```

### Б.8 Ирмэгийн дүрсийг урьдчилан татах

```bash
cd ~/cnc302/edge
docker compose pull                # eclipse-mosquitto ~10 MB, хурдан
python3 -m venv .venv
.venv/bin/pip install -r agent/requirements.txt
```

> `numpy`-г Pi 3B дээр эх кодоос барих шаардлагагүй — piwheels-ээс бэлэн хувилбар ирнэ. 2–4 минут болно.

---

## В. 💻🥧 Хоёр машиныг холбох

### В.1 Гүүрийг асаах

🥧 Pi дээр:
```bash
cd ~/cnc302/edge
make up
make link            # Ctrl+C-ээр зогсооно
```

`.../bridge/state 1` гарвал **гүүр холбогдсон**. `0` бол — тасарсан.

### В.2 Хоёр талаас шалгах

🥧 Pi дээр (нэг терминал):
```bash
cd ~/cnc302/edge && make agent
```

💻 Компьютер дээр (өөр терминал):
```bash
mosquitto_sub -h localhost -t 'cnc302/#' -v
```

Pi-гийн телеметр компьютер дээр гарч ирэх ёстой. **Гарч ирэхгүй бол Лаб 1 эхлэхгүй.** Шалгах дараалал:

| Шалгах зүйл | Комманд | Хүлээгдэх |
|---|---|---|
| 1. Pi үүлийг харж байна уу | 🥧 `ping -c3 $CLOUD_HOST` | хариу ирнэ |
| 2. Порт нээлттэй юу | 🥧 `nc -vz $CLOUD_HOST 1883` | succeeded |
| 3. Гүүрний тохиргоо | 🥧 `docker compose logs mosquitto \| grep -i bridge` | "Connecting bridge" |
| 4. Сэдвийн угтвар | 🥧 `grep '^topic' mosquitto/conf.d/bridge.conf` | `cnc302/shutis/#` |
| 5. Агентын сэдэв | 🥧 `grep SITE .env` | `shutis` |

3-р алхам "Broken pipe" эсвэл "Connection refused" бол → А.6 галт хана.
4 ба 5-р алхмын `SITE` зөрүүтэй бол → мессеж дамжихгүй. Энэ бол **хамгийн түгээмэл алдаа**.

### В.3 VS Code Remote-SSH холболт

1. VS Code → `Ctrl+Shift+P` → **Remote-SSH: Add New SSH Host**
2. `ssh -i ~/.ssh/cnc302 cnc302@pi-team03.local`
3. Холбогдоод `~/cnc302` фолдерыг нээнэ
4. VS Code-ийн терминал одоо Pi дээр ажиллана

> Pi 3B дээр VS Code-ийн сервер 150–250 MiB иднэ. Хэмжилт хийхийн өмнө **VS Code-ийн холболтыг таслах** — эс бөгөөс санах ойн тоо гажина. `pkill -f vscode-server`.

---

## Г. Бэлэн байдлын шалгалт

Лаб 1-д ирэхээс өмнө эдгээр бүгд ✔ байх ёстой:

### 💻 Зөөврийн компьютер

- [ ] `docker info` → санах ой ≥ 6 GB
- [ ] `cd stack && make health` → бүх мөр 200
- [ ] `make ip` → LAN IP тодорхой
- [ ] `mosquitto_sub -h localhost -t 'cnc302/#' -v` ажиллаж байна
- [ ] `python tools/sim_device.py --dry-run` ажиллаж байна
- [ ] Галт ханд 1883 порт нээлттэй (Windows)

### 🥧 Raspberry Pi 3B

- [ ] `uname -m` → **aarch64** (armv7l бол 64-bit OS дахин суулгана)
- [ ] `ssh` түлхүүрээр нууц үггүй холбогдож байна
- [ ] `docker run --rm hello-world` ажиллаж байна
- [ ] `free -h` → Swap 2.0Gi, Mem нийт ~925Mi
- [ ] `cat /proc/cgroups | grep memory` → эхний багана 1
- [ ] `vcgencmd get_throttled` → **0x0**
- [ ] `timedatectl status` → synchronized: yes
- [ ] `cd edge && make check` → бүгд OK

### 💻🥧 Хамтдаа

- [ ] `make link` → `bridge/state 1`
- [ ] Pi-гийн агентын телеметр компьютер дээр харагдаж байна
- [ ] Багийн Git санд эхний commit хийгдсэн, багш унших эрхтэй

Аль нэг нь ✘ бол лабораторийн өмнөх өдөр багшид хандана. **Лабораторийн 4 цагийг орчин тохируулахад зарцуулж болохгүй.**
