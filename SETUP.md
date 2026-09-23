# SETUP — Лаб 1-ээс өмнө нэг удаа хийх бэлтгэл

Хугацаа: **60–90 минут** (Лаб 8-ын VM-ийг оруулбал +30 минут). Үүнийг лабораторийн цагаар биш, **I–II долоо хоногийн бие даалтаар** гүйцэтгэнэ. Лаб 1 эхлэхэд энэ бүхэн бэлэн байх ёстой.

Бэлтгэл нь хоёр машин дээр явагдана: **💻 зөөврийн компьютер** (үүл) ба **🥧 Raspberry Pi 3B** (ирмэг). Аль хэсэг хаана хийгдэхийг тэмдэглэгээгээр заасан. Лаб 8-д гурав дахь зангилаа болох **🖥️ K3s server VM** (зөөврийн компьютер дээрх виртуал машин) нэмэгдэнэ — А.8.

---

## А. 💻 Зөөврийн компьютер дээр

### А.1 Шаардлагатай програм

| Програм | Шалгах комманд | Тайлбар |
|---|---|---|
| Git | `git --version` | 2.30+ |
| Python | `python3 --version` | 3.10+ |
| Docker Desktop | `docker compose version` | v2.20+; Лаб 8-ын `docker save --platform`-д Docker API 1.48+ (шинэ хувилбар) |
| VS Code | — | + **Remote - SSH**, **Docker**, **YAML** өргөтгөл |
| SSH клиент | `ssh -V` | Windows 10/11-д суулгаастай |
| MQTT Explorer | — | http://mqtt-explorer.com (сонголт: `mosquitto_sub`) |
| VirtualBox | `VBoxManage --version` | Зөвхөн Лаб 8 (А.8) |

**Зөөврийн компьютерийн санах ой:** Docker Desktop-д 6 GB + Лаб 8-ын VM-д 4 GB + хост OS → **16 GB RAM тав тухтай**. 8 GB-тай бол Лаб 8-д VM-д 2 GB өгч, Ollama-г зогсоож ажиллана (`lab08/k3s/README.md`).

### А.2 Docker Desktop-ийн санах ой (ЗААВАЛ)

Docker Desktop-ийн баримтаар Linux VM-д анхдагчаар **хост компьютерийн санах ойн 50%**-ийг өгдөг. Бидэнд **6 GB** хэрэгтэй (Лаб 8-д Ollama). Тохируулах газар нь backend-ээс хамаарна:

- **Windows + WSL 2 backend (анхдагч):** Resources-ийн Memory гулсуур **байхгүй** — санах ойг WSL 2-ын VM-д `%UserProfile%\.wslconfig` файлаар өгнө:
  ```ini
  [wsl2]
  memory=6GB
  ```
  Дараа нь PowerShell-д `wsl --shutdown` хийж, Docker Desktop-ийг дахин асаана. (Windows-ийн *WSL Settings* програмаар ч тохируулж болно.)
- **macOS, Linux, Windows Hyper-V backend:** **Settings → Resources → Advanced → Memory limit → 6 GB** (16 GB-тай бол 8 GB) → *Apply & restart*.

```bash
docker info --format '{{.MemTotal}}' | awk '{printf "Docker-т %.1f GB\n", $1/1024/1024/1024}'
```

4 GB-аас бага бол Лаб 8-д `ai` профайл ажиллахгүй.

> Албан ёсны баримт: [Docker Desktop — Settings (Resources)](https://docs.docker.com/desktop/settings-and-maintenance/settings/) · [WSL — .wslconfig](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)

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

Windows Defender Firewall гаднаас ирэх холболтыг анхдагчаар хаадаг тул Pi-гаас ирэх портуудыг нээнэ: 1883 (MQTT, гүүр), 8883 (MQTT/TLS, Лаб 2), 8090 (registry/OTA, Лаб 2), 8181 (InfluxDB), 3000 (Grafana):

```powershell
# PowerShell (Administrator)
New-NetFirewallRule -DisplayName "CNC302 cloud" -Direction Inbound `
  -Protocol TCP -LocalPort 1883,8883,8090,8181,3000 -Action Allow -Profile Private
```

> Зөвхөн **Private** профайлд нээ (Windows-д сүлжээгээ "Private" гэж тохируулсан байх ёстой). Нийтийн сүлжээнд задгай MQTT брокер орхиж болохгүй.
>
> Албан ёсны баримт: [New-NetFirewallRule](https://learn.microsoft.com/en-us/powershell/module/netsecurity/new-netfirewallrule)

### А.7 SSH түлхүүр үүсгэх

```bash
ssh-keygen -t ed25519 -C "<таны-имэйл>" -f ~/.ssh/cnc302
```

> Нууц түлхүүрийг (`cnc302`) **хэзээ ч** Git санд оруулахгүй.

### А.8 🖥️ Лаб 8-ын K3s server VM (Лаб 8-аас өмнө хийнэ)

Лаб 8-д K3s-ийн **server** нь зөөврийн компьютер дээрх VM-д, Pi 3B нь **agent** болж нэгдэнэ. K3s-ийн албан ёсны доод шаардлага: server **2 цөм / 2 GB**, agent **1 цөм / 512 MB** — 1 GB-тай Pi server-т хүрэлцэхгүй.

| Тохиргоо | Утга |
|---|---|
| Гипервизор | Oracle VirtualBox |
| Зочин OS | **Ubuntu Server LTS** amd64 — одоогийн LTS нь **26.04** (24.04 LTS ч дэмжигдсэн хэвээр) |
| vCPU / RAM / диск | **≥ 2 vCPU**, **4 GB** (доод 2 GB), 20 GB |
| Сүлжээ | **Bridged Adapter** (LAN-д холбогдсон физик адаптер), NAT адаптер нэмэхгүй |
| Суулгахдаа | **OpenSSH server**-ийг сонго |

Дэлгэрэнгүй алхам ба K3s-ийн суулгалт: `lab08/k3s/README.md` §3.1–3.2.

> ⚠ **Windows дээр Hyper-V ба VirtualBox:** Docker Desktop-ийн WSL 2 backend нь Windows-ийн гипервизорыг (Hyper-V платформ) асаадаг. VirtualBox-ийн гарын авлагаар Hyper-V ажиллаж байгаа хост дээр VirtualBox ажиллах боловч *"significant Oracle VirtualBox performance degradation"* гарч болно; VirtualBox Hyper-V-г виртуалчлалын хөдөлгүүр болгон автоматаар ашиглах бөгөөд үүнд **Windows Hypervisor Platform**-ийг нэмж идэвхжүүлсэн байх шаардлагатай. VM-ийн цонхны CPU дүрс (яст мэлхий) энэ горимыг заана. VM-д 2 vCPU-гээс бага бүү өг.
>
> Албан ёсны баримт: [VirtualBox User Manual — Using Hyper-V with Oracle VirtualBox](https://www.virtualbox.org/manual/UserManual.html) · [Ubuntu release cycle](https://ubuntu.com/about/release-cycle) · [K3s Requirements](https://docs.k3s.io/installation/requirements)

---

## Б. 🥧 Raspberry Pi 3B дээр

### Б.0 Тоног төхөөрөмжийн шалгуур

| Зүйл | Шаардлага | Яагаад |
|---|---|---|
| Тэжээл | **5 V / 2.5 A** (албан ёсны 12.5 W Micro USB адаптер) | Сул тэжээл → хүчдэл унана (`get_throttled`-ийн бит 0) → бүх хэмжилт гажина |
| Хөргөлт | Наалдацтай хөргөгч, боломжтой бол сэнс | Албан ёсны баримтаар 80–85 °C-д Arm цөмийн давтамж аажмаар буурна |
| microSD | **A1 эсвэл A2**, 16 GB+ | Хямд карт дээр persistence, swap бичилт удаан |
| Сүлжээ | **Кабель** (Wi-Fi биш) | Pi 3B-ийн Wi-Fi нь зөвхөн 2.4 GHz, лабораторид бөглөрдөг |

Pi 3B-ийн албан ёсны үзүүлэлт: BCM2837, 4 × Cortex-A53 (Armv8) @ 1.2 GHz, **1 GB** RAM, 100 Mb/s Ethernet, 4 × USB 2.0, 2.4 GHz 802.11n Wi-Fi, microSD.

### Б.1 Систем суулгах

1. Raspberry Pi Imager → **Raspberry Pi OS Lite (64-bit)** — одоогийн хувилбар нь **Debian Trixie** дээр суурилсан (өмнөх нь Bookworm). Pi 3B нь 64-бит процессортой тул 64-бит хувилбарыг албан ёсоор дэмжинэ.

   > ⚠ **64-bit заавал.** Манай бүх дүрс (image) ба Python wheel (`ai-edge-litert` г.м.) arm64-д зориулагдсан. Docker Engine v29-өөс эхлэн Raspberry Pi OS 32-bit (armhf)-д шинэ багц гаргахаа больсон. Imager 32-bit санал болговол `Raspberry Pi OS (other)` цэснээс **Lite (64-bit)**-ыг сонгоно.

   > ⚠ **Lite заавал.** Ширээний орчин 1 GB-д хэт үнэтэй — Lite нь *"command-line-only"* хувилбар.

2. Imager-ийн OS тохируулгын (customisation) хэсэгт:
   - Хостын нэр: `pi-<багийн-нэр>` (жишээ: `pi-team03`)
   - Хэрэглэгч: `cnc302`, хүчтэй нууц үг (`edge/agent/cnc302-edge-agent.service` энэ нэрийг хүлээнэ)
   - SSH идэвхжүүлэх → **public-key authentication only** → А.7-д үүсгэсэн `cnc302.pub`-ийн агуулгыг наах
   - Кабель сүлжээ (Wi-Fi зөвхөн шаардлагатай үед)

> Албан ёсны баримт: [Raspberry Pi OS](https://www.raspberrypi.com/documentation/computers/os.html) ([эх: GitHub](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/os/rpi-os-introduction.adoc))

### Б.2 Эхний холболт ба шинэчлэл

```bash
ssh -i ~/.ssh/cnc302 cnc302@pi-team03.local

sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git curl jq htop iotop stress-ng mosquitto-clients \
                    python3-venv python3-dev
sudo reboot
```

### Б.3 GPU-гийн санах ой (`gpu_mem`) — хэмжиж шийднэ

Raspberry Pi-гийн баримтаар 1 GB-тай загварт `gpu_mem`-ийн **анхдагч утга 76** MiB. Гэхдээ баримт `gpu_mem`-ийг **legacy** тохиргоонд ангилж, *Raspberry Pi OS Bookworm болон түүнээс хойшхи хувилбарт ажиллахгүй, албан ёсоор дэмжигдэхгүй* гэж тэмдэглэсэн. Тиймээс «N MiB хэмнэнэ» гэж амлахгүй — **өмнө ба дараа нь хэмжинэ**:

```bash
grep MemTotal /proc/meminfo          # (1) өмнөх утгыг тэмдэглэ
vcgencmd get_mem gpu
echo 'gpu_mem=16' | sudo tee -a /boot/firmware/config.txt
sudo reboot
# дахин нэвтэрсний дараа:
grep MemTotal /proc/meminfo          # (2) өөрчлөгдсөн үү?
vcgencmd get_mem gpu
```

(1) ба (2)-ын зөрүүг Лаб 1-ийн хүснэгтэд бич. Зөрүүгүй бол энэ мөр таны OS дээр нөлөөгүй гэсэн үг — буруу биш, **хэмжилт**.

> Албан ёсны баримт: [Legacy config.txt — gpu_mem](https://www.raspberrypi.com/documentation/computers/legacy_config_txt.html#gpu_mem) ([эх: GitHub](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/legacy_config_txt/memory.adoc))

### Б.4 Docker суулгах

Pi 3B дээрх **64-бит** Raspberry Pi OS бол Debian-д суурилсан тул Docker-ийн **Debian** зааврыг (`apt` репозитор) дагана. `get.docker.com` convenience script-ийг Docker өөрөө *зөвхөн туршилт ба хөгжүүлэлтийн орчинд* зөвлөдөг бөгөөд одоо суусан Docker-ийг шинэчлэхэд зориулагдаагүй.

```bash
# 1. Зөрчилдөх албан бус багцыг устгах (байхгүй бол алгасна)
sudo apt remove $(dpkg --get-selections docker.io docker-compose docker-doc docker-buildx podman-docker containerd runc | cut -f1)

# 2. Docker-ийн apt репозитор
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update

# 3. Суулгах
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 4. sudo-гүй ажиллуулах
sudo usermod -aG docker $USER
newgrp docker                      # эсвэл гараад дахин нэвтэрнэ

docker --version
docker compose version             # v2.20+ байх ёстой
docker run --rm hello-world
```

> ⚠ `docker` бүлэгт орсон хэрэглэгч root-той дүйцэх эрхтэй болдог (Docker-ийн post-install баримт) — Pi-гийн `cnc302` хэрэглэгчийн нууц үгийг хамгаал.

Docker-ийн лог microSD-г элээхээс сэргийлэх (`log-opts`-ийн утгууд **мөр** байх ёстой):

```bash
sudo tee /etc/docker/daemon.json > /dev/null <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "5m", "max-file": "2" }
}
EOF
sudo systemctl restart docker      # зөвхөн ШИНЭЭР үүсэх контейнерт үйлчилнэ
```

> Албан ёсны баримт: [Install Docker Engine on Debian](https://docs.docker.com/engine/install/debian/) · [Linux post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/) · [JSON File logging driver](https://docs.docker.com/engine/logging/drivers/json-file/)

### Б.5 Солих санах ой (swap) ба cgroup (ЗААВАЛ)

**Swap.** 1 GB RAM дээр swap нь Лаб 4–8-д OOM-оос хамгаалах **аюулгүйн сүлжээ**. Курсын бүх заавар **2 GiB** swap гэж тооцсон. Raspberry Pi OS-ийн хувилбараас хамаарч swap-ыг удирдах хэрэгсэл өөр:

```bash
swapon --show; free -h                      # одоогийн байдал
test -e /etc/rpi/swap.conf && echo "rpi-swap" || echo "rpi-swap алга"
systemctl is-enabled dphys-swapfile 2>/dev/null
```

**(а) `rpi-swap` байгаа бол (шинэ зураг, Trixie).** Raspberry Pi-гийн `rpi-swap` багц `dphys-swapfile`-ийг орлох зорилготой; анхдагч `Mechanism=auto` нь одоогоор **zram+file** (шахсан RAM swap + ховор бичигддэг файл), zram-ын хэмжээ анхдагчаар RAM-тай тэнцүү (2048 MiB-ээр хязгаарлагдана) — Pi 3B дээр ~0.9 GiB. Бид `swap.conf(5)`-ын **албан ёсны "Example 1"**-ийг дагаж 2 GiB-ийн уламжлалт swap файл тавина:

```bash
sudo mkdir -p /etc/rpi/swap.conf.d/
sudo tee /etc/rpi/swap.conf.d/80-use-swapfile.conf > /dev/null <<EOF
[Main]
Mechanism=swapfile

[File]
FixedSizeMiB=2048
EOF
sudo reboot                        # swap-ын тохиргоо ЗӨВХӨН дахин ачаалахад хэрэгжинэ
```

> Анхдагч zram+file-ийг үлдээх нь microSD-г бага элээнэ (албан ёсны зорилго нь тэр). Энэ тохиолдолд `make check`-ийн swap мөр ✗ гарах бөгөөд Лаб 1–8-ын "2.0Gi" гэсэн хүлээлтийн оронд өөрийн утгаа тайландаа бич.

**(б) `rpi-swap` байхгүй, `dphys-swapfile` ажиллаж байгаа бол (хуучин Bookworm зураг).** Энэ багцын тохиргоо Raspberry Pi-гийн баримтад ороогүй тул доорх нь уламжлалт арга:

```bash
sudo dphys-swapfile swapoff
sudo sed -i 's/^#\?CONF_SWAPSIZE=.*/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

Аль ч тохиолдолд шалгах: `free -h` → `Swap: 2.0Gi`.

> **Санамж:** swap файл microSD дээр байгаа тул **маш удаан**. Энэ бол гүйцэтгэлийн шийдэл биш. Лаб 4-д swap ажиллаж эхэлбэл (`vmstat 1`-ийн `si/so` багана 0-ээс их) та аль хэдийн хязгаарт хүрсэн — тэр нь хэмжилт өөрөө юм.
>
> Албан ёсны эх: [raspberrypi/rpi-swap — README, swap.conf(5)](https://github.com/raspberrypi/rpi-swap)

**cgroup.** K3s-ийн баримтаар стандарт Raspberry Pi OS cgroup-ийн санах ойн хянагчийг идэвхжүүлээгүй эхэлдэг; Лаб 8-ын K3s agent ба `docker stats`-ын санах ойн тоонд хэрэгтэй. Параметрийг `/boot/firmware/cmdline.txt`-ийн **цорын ганц мөрийн төгсгөлд** залгана (Debian 11 ба түүнээс өмнөх зурагт зам нь `/boot/cmdline.txt`). Raspberry Pi-гийн баримт: бүх параметр нэг мөрөнд байх ёстой — шинэ мөр оруулбал түүнээс хойшхыг цөм үл тоомсорлоно.

```bash
grep -q 'cgroup_memory=1' /boot/firmware/cmdline.txt || \
  sudo sed -i '1 s/$/ cgroup_memory=1 cgroup_enable=memory/' /boot/firmware/cmdline.txt
cat /boot/firmware/cmdline.txt    # НЭГ мөр байх ёстой
sudo reboot
```

Шалгах:
```bash
grep -w memory /sys/fs/cgroup/cgroup.controllers   # "memory" гарах ёстой
free -m | head -2                                   # MemTotal-ийг Лаб 1-д бичнэ
```

> Албан ёсны баримт: [K3s Requirements — Raspberry Pi (cgroups)](https://docs.k3s.io/installation/requirements) · [Kernel command line (cmdline.txt)](https://www.raspberrypi.com/documentation/computers/configuration.html#configure-the-kernel-command-line) ([эх: GitHub](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/configuration/boot-behaviour.adoc))

### Б.6 Цагийн синхрончлол (ЗААВАЛ)

Лаб 3, Лаб 5-ын саатлын хэмжилт цагийн зөрүүнээс шалтгаалж утгагүй болдог. Pi 3B-д бодит цагийн цаг (RTC) **байхгүй** — асаах бүрд NTP-ээс цагаа авдаг.

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

> `.env`-д тайлбарыг **тусдаа мөрөнд** бич (`KEY=утга  # тайлбар` БИШ): systemd-ийн `EnvironmentFile=` мөрийн дундах `#`-ийг утгын нэг хэсэг гэж уншдаг.

### Б.8 Ирмэгийн дүрс ба Python орчин

```bash
cd ~/cnc302/edge
docker compose pull                # eclipse-mosquitto, хэдэн MB
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r agent/requirements.txt   # paho-mqtt, numpy, ai-edge-litert
.venv/bin/python -c "from ai_edge_litert.interpreter import Interpreter; print('LiteRT OK')"
```

> `ai-edge-litert` (LiteRT — TensorFlow Lite-ийн шинэ нэр) нь PyPI дээр Python 3.11 (Bookworm) ба 3.13 (Trixie)-д зориулсан `manylinux_2_27_aarch64` wheel-тэй; `numpy` ч мөн aarch64 wheel-тэй тул Pi дээр эх кодоос барихгүй. `No matching distribution` гарвал `uname -m` → `aarch64` эсэхийг шалга. Хуучин `tflite-runtime` (сүүлийн хувилбар 2.14, 2023) нь зөвхөн нөөц хувилбар.
>
> Албан ёсны баримт: [LiteRT — Migrate from tflite-runtime](https://ai.google.dev/edge/litert/migration) · [pypi: ai-edge-litert](https://pypi.org/project/ai-edge-litert/)

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

3-р алхамд "Connection refused" эсвэл удаа дараа тасарч байвал → А.6 галт хана.
4 ба 5-р алхмын `SITE` зөрүүтэй бол → мессеж дамжихгүй. Энэ бол **хамгийн түгээмэл алдаа**.

### В.3 VS Code Remote-SSH холболт

1. VS Code → `Ctrl+Shift+P` → **Remote-SSH: Add New SSH Host**
2. `ssh -i ~/.ssh/cnc302 cnc302@pi-team03.local`
3. Холбогдоод `~/cnc302` фолдерыг нээнэ
4. VS Code-ийн терминал одоо Pi дээр ажиллана

> VS Code-ийн баримтаар Remote-SSH-ийн алсын хостод **1 GB RAM шаардлагатай, 2 GB RAM ба 2 цөм зөвлөмжтэй** — Pi 3B яг доод хязгаар дээр. Дэмжигдэх платформ: Debian 64-бит ARMv8 (AArch64), kernel ≥ 4.18, glibc ≥ 2.28; ARM хост дээр зарим өргөтгөлийн native модуль ажиллахгүй байж болно. Хэмжилт хийхийн өмнө **VS Code-ийн холболтыг таслах** — эс бөгөөс санах ойн тоо гажина (`pkill -f vscode-server`).
>
> Албан ёсны баримт: [Remote Development using SSH — System requirements](https://code.visualstudio.com/docs/remote/ssh) · [Remote Development with Linux](https://code.visualstudio.com/docs/remote/linux)

---

## Г. Бэлэн байдлын шалгалт

Лаб 1-д ирэхээс өмнө эдгээр бүгд ✔ байх ёстой:

### 💻 Зөөврийн компьютер

- [ ] `docker info` → санах ой ≥ 6 GB
- [ ] `cd stack && make health` → бүх мөр 200
- [ ] `make ip` → LAN IP тодорхой
- [ ] `mosquitto_sub -h localhost -t 'cnc302/#' -v` ажиллаж байна
- [ ] `python tools/sim_device.py --dry-run` ажиллаж байна
- [ ] Галт ханд 1883, 8883, 8090 порт нээлттэй (Windows)

### 🥧 Raspberry Pi 3B

- [ ] `uname -m` → **aarch64** (armv7l бол 64-bit OS дахин суулгана)
- [ ] `ssh` түлхүүрээр нууц үггүй холбогдож байна
- [ ] `docker run --rm hello-world` ажиллаж байна
- [ ] `free -h` → Swap 2.0Gi; `MemTotal`-ийг тэмдэглэсэн (Б.3)
- [ ] `grep -w memory /sys/fs/cgroup/cgroup.controllers` → `memory` агуулна
- [ ] `vcgencmd get_throttled` → **0x0**
- [ ] `timedatectl status` → synchronized: yes
- [ ] `cd edge && make check` → бүгд OK

### 💻🥧 Хамтдаа

- [ ] `make link` → `bridge/state 1`
- [ ] Pi-гийн агентын телеметр компьютер дээр харагдаж байна
- [ ] Багийн Git санд эхний commit хийгдсэн, багш унших эрхтэй

### 🖥️ Лаб 8-аас өмнө

- [ ] А.8-ын VM асаж, `ssh`-ээр холбогдож байна; `ip -4 addr` → LAN-ын хаяг (10.0.2.x БИШ)

Аль нэг нь ✘ бол лабораторийн өмнөх өдөр багшид хандана. **Лабораторийн 4 цагийг орчин тохируулахад зарцуулж болохгүй.**

---

## Эх сурвалж

| # | Эх сурвалж | Юуг баталгаажуулсан | Хандсан |
|---|---|---|---|
| 1 | [Docker Desktop — Settings](https://docs.docker.com/desktop/settings-and-maintenance/settings/) | Memory limit: Mac, Linux, Windows Hyper-V; анхдагч нь хостын 50%; WSL 2 горимд санах ойг WSL 2 VM дээр тохируулна | 2026-09 |
| 2 | [WSL — Advanced settings configuration (.wslconfig)](https://learn.microsoft.com/en-us/windows/wsl/wsl-config) | `%UserProfile%\.wslconfig`, `[wsl2] memory=`, анхдагч 50%, `wsl --shutdown` | 2026-09 |
| 3 | [New-NetFirewallRule](https://learn.microsoft.com/en-us/powershell/module/netsecurity/new-netfirewallrule) | `-LocalPort` порт/жагсаалт, `-Profile Private` | 2026-09 |
| 4 | [VirtualBox User Manual](https://www.virtualbox.org/manual/UserManual.html) | Hyper-V ажиллаж буй хост дээр гүйцэтгэл буурна, Windows Hypervisor Platform шаардлагатай; Bridged networking | 2026-09 |
| 5 | [Ubuntu release cycle](https://ubuntu.com/about/release-cycle), [Ubuntu Server download](https://ubuntu.com/download/server) | Одоогийн LTS: 26.04 (24.04 LTS дэмжигдсэн) | 2026-09 |
| 6 | [K3s — Requirements](https://docs.k3s.io/installation/requirements) | server 2 цөм/2 GB, agent 1 цөм/512 MB; Raspberry Pi OS-д `cgroup_memory=1 cgroup_enable=memory`, `/boot/firmware/cmdline.txt` (Debian 11 ба өмнөх: `/boot/cmdline.txt`) | 2026-09 |
| 7 | [Raspberry Pi hardware](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html) ([эх](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/raspberry-pi/introduction.adoc)), [BCM2837](https://www.raspberrypi.com/documentation/computers/processors.html#bcm2837) ([эх](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/processors/bcm2837.adoc)) | Pi 3B: BCM2837, 4×Cortex-A53 @1.2 GHz, 1 GB, 100 Mb/s Ethernet, 4×USB 2.0, 2.4 GHz Wi-Fi | 2026-09 |
| 8 | [Getting started — power supply](https://www.raspberrypi.com/documentation/computers/getting-started.html) ([эх](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/getting-started/setting-up.adoc)) | Pi 3 (бүх загвар): 5 V / 2.5 A, 12.5 W Micro USB | 2026-09 |
| 9 | [Frequency management and thermal control](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#frequency-management-and-thermal-control) ([эх](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/raspberry-pi/frequency-management.adoc)) | 80–85 °C-д Arm цөм аажмаар throttle, 85 °C хатуу хязгаар | 2026-09 |
| 10 | [vcgencmd get_throttled](https://www.raspberrypi.com/documentation/computers/os.html#vcgencmd) ([эх](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/os/graphics-utilities.adoc)) | бит 0 = undervoltage, бит 2 = throttled, бит 16/18 = өмнө нь болсон | 2026-09 |
| 11 | [Raspberry Pi OS](https://www.raspberrypi.com/documentation/computers/os.html) ([эх](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/os/rpi-os-introduction.adoc)) | Сүүлийн хувилбар Trixie (өмнөх Bookworm); Lite = command-line-only; 64-бит нь Pi 3-д | 2026-09 |
| 12 | [Legacy config.txt — gpu_mem](https://www.raspberrypi.com/documentation/computers/legacy_config_txt.html) ([эх 1](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/legacy_config_txt/legacy.adoc), [эх 2](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/legacy_config_txt/memory.adoc)) | 1 GB-д анхдагч 76; legacy — Bookworm+ дээр ажиллахгүй, албан ёсоор дэмжигдэхгүй; доод утга 16 | 2026-09 |
| 13 | [Kernel command line](https://www.raspberrypi.com/documentation/computers/configuration.html) ([эх](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/configuration/boot-behaviour.adoc)) | `cmdline.txt`-ийн бүх параметр нэг мөрөнд | 2026-09 |
| 14 | [raspberrypi/rpi-swap](https://github.com/raspberrypi/rpi-swap) (README, `man/man5/swap.conf.5`) | `dphys-swapfile`-ийг орлоно; `/etc/rpi/swap.conf.d/`; `Mechanism=auto` = zram+file; Example 1 (`swapfile`, `FixedSizeMiB=2048`); өөрчлөлтийн дараа reboot | 2026-09 |
| 15 | [Install Docker Engine on Debian](https://docs.docker.com/engine/install/debian/) | Trixie 13 / Bookworm 12, arm64; apt репозиторын алхам; convenience script зөвхөн туршилт/хөгжүүлэлтэд | 2026-09 |
| 16 | [Install Docker Engine on Raspberry Pi OS (32-bit)](https://docs.docker.com/engine/install/raspberry-pi-os/) | Engine v28 нь armhf-ийн сүүлийнх; 64-бит ARM-д Debian arm64 багц | 2026-09 |
| 17 | [Linux post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/) | `usermod -aG docker`, `newgrp docker`, docker бүлгийн эрсдэл | 2026-09 |
| 18 | [JSON File logging driver](https://docs.docker.com/engine/logging/drivers/json-file/) | `daemon.json`-ийн `log-opts` мөр утгатай; зөвхөн шинэ контейнерт | 2026-09 |
| 19 | [VS Code — Remote Development using SSH](https://code.visualstudio.com/docs/remote/ssh) | 1 GB RAM шаардлагатай, 2 GB + 2 цөм зөвлөмжтэй | 2026-09 |
| 20 | [VS Code — Remote Development with Linux](https://code.visualstudio.com/docs/remote/linux) | Debian 64-бит ARMv8 (AArch64), kernel ≥ 4.18, glibc ≥ 2.28; ARM дээр өргөтгөлийн native модулийн эрсдэл | 2026-09 |
| 21 | [pypi: ai-edge-litert](https://pypi.org/project/ai-edge-litert/), [pypi: numpy](https://pypi.org/project/numpy/) | ai-edge-litert 2.2.0: cp311/cp313 `manylinux_2_27_aarch64`; numpy aarch64 wheel | 2026-09 |
