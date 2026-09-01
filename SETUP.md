# SETUP — Лаб 1-ээс өмнө нэг удаа хийх бэлтгэл

Хугацаа: **40–60 минут**. Үүнийг лабораторийн цагаар биш, **I долоо хоногийн бие даалтаар** гүйцэтгэнэ. Лаб 1 эхлэхэд энэ бүхэн бэлэн байх ёстой.

---

## А. Зөөврийн компьютер дээр

### А.1 Шаардлагатай програм

| Програм | Шалгах комманд | Тайлбар |
|---|---|---|
| Git | `git --version` | 2.30+ |
| Python | `python3 --version` | 3.10+ |
| VS Code | — | + **Remote - SSH**, **Docker**, **YAML** өргөтгөл |
| SSH клиент | `ssh -V` | Windows 10/11-д суулгаастай |
| MQTT Explorer | — | http://mqtt-explorer.com (сонголт: `mosquitto_sub`) |

### А.2 Python орчин

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

### А.3 SSH түлхүүр үүсгэх

```bash
ssh-keygen -t ed25519 -C "<таны-имэйл>" -f ~/.ssh/cnc302
```

> Нууц түлхүүрийг (`cnc302`) **хэзээ ч** Git санд оруулахгүй.

---

## Б. Raspberry Pi 5 дээр

### Б.1 Систем суулгах

1. Raspberry Pi Imager → **Raspberry Pi OS Lite (64-bit)** (ширээний орчин шаардлагагүй)
2. Imager-ийн тохиргооны цэсэнд (⚙):
   - Хостын нэр: `pi-<багийн-нэр>` (жишээ: `pi-team03`)
   - Хэрэглэгч: `cnc302`, хүчтэй нууц үг
   - SSH идэвхжүүлэх → **Allow public-key authentication only** → А.3-д үүсгэсэн `cnc302.pub`-ийн агуулгыг наах
   - Wi-Fi эсвэл кабель сүлжээ (лабораторид **кабель** илүү тогтвортой)
3. NVMe SSD байвал үүнийг ашиглана — microSD дээр InfluxDB, Postgres удаан ажиллана.

### Б.2 Эхний холболт ба шинэчлэл

```bash
ssh -i ~/.ssh/cnc302 cnc302@pi-team03.local

sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git curl jq htop iotop stress-ng
sudo reboot
```

### Б.3 Docker суулгах

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker                      # эсвэл дахин нэвтэрнэ

docker --version
docker compose version             # v2.20+ байх ёстой
docker run --rm hello-world
```

### Б.4 Санах ой, солих файлын тохиргоо (ЗААВАЛ)

ThingsBoard + Postgres нь эхлэх үедээ санах ой ихээр шаарддаг. Анхны тохиргоогоор Pi-гийн swap ердөө 200 MB — энэ нь Лаб 1-д "container killed (OOM)" алдаа өгнө.

```bash
sudo dphys-swapfile swapoff
sudo sed -i 's/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
free -h                            # Swap: 2.0Gi байх ёстой
```

cgroup санах ойн хязгаарлалтыг идэвхжүүлэх (`docker stats`-ын санах ойн тоо зөв гарахад шаардлагатай):

```bash
sudo sed -i '1 s/$/ cgroup_enable=memory cgroup_memory=1/' /boot/firmware/cmdline.txt
sudo reboot
```

Шалгах:
```bash
cat /proc/cgroups | grep memory   # эхний баганад 1 байх ёстой
```

### Б.5 Цагийн синхрончлол (ЗААВАЛ)

Лаб 3, Лаб 5-ын саатлын хэмжилт цагийн зөрүүнээс шалтгаалж утгагүй болдог.

```bash
timedatectl set-timezone Asia/Ulaanbaatar
sudo timedatectl set-ntp true
timedatectl status                 # "System clock synchronized: yes"
```

### Б.6 Сангаа Pi дээр байрлуулах

```bash
mkdir -p ~/cnc302 && cd ~/cnc302
git clone <багийн-сангийн-хаяг> .
cp stack/.env.example stack/.env
nano stack/.env                    # нууц үгсээ солино
```

---

## В. VS Code Remote-SSH холболт

1. VS Code → `Ctrl+Shift+P` → **Remote-SSH: Add New SSH Host**
2. `ssh -i ~/.ssh/cnc302 cnc302@pi-team03.local`
3. Холбогдоод `~/cnc302` фолдерыг нээнэ
4. VS Code-ийн терминал одоо Pi дээр ажиллана

**Порт дамжуулалт** (хөтчөөрөө Pi-гийн үйлчилгээнд хандах): VS Code-ийн `PORTS` таб → `Forward a Port` → 18083, 8080, 3000, 8181, 1880. Ингэснээр зөөврийн компьютерийн хөтөч дээр `localhost:8080` гэж ThingsBoard-д ханддаг болно.

> Хэрэв VS Code ашиглахгүй бол SSH туннел:
> ```bash
> ssh -i ~/.ssh/cnc302 -L 8080:localhost:8080 -L 3000:localhost:3000 \
>     -L 18083:localhost:18083 -L 8181:localhost:8181 cnc302@pi-team03.local
> ```

---

## Г. Дүрсүүдийг урьдчилан татах (ЧУХАЛ)

Лабораторийн цагаар 3 GB дүрс татахад 20–30 минут алдана. **Бие даалтын цагаар** урьдчилан татна:

```bash
cd ~/cnc302/stack
docker compose --profile core pull
```

Татаж дууссаны дараа шалгах:
```bash
docker images --format '{{.Repository}}:{{.Tag}}\t{{.Size}}'
```

---

## Д. Бэлэн байдлын шалгалт

Лаб 1-д ирэхээс өмнө эдгээр бүгд ✔ байх ёстой:

- [ ] `ssh` түлхүүрээр Pi-д нууц үггүй холбогдож байна
- [ ] `docker run --rm hello-world` ажиллаж байна
- [ ] `free -h` → Swap 2.0Gi
- [ ] `cat /proc/cgroups | grep memory` → эхний багана 1
- [ ] `timedatectl status` → synchronized: yes
- [ ] `docker compose --profile core pull` алдаагүй дууссан
- [ ] VS Code Remote-SSH-ээр `~/cnc302` нээгдэж байна
- [ ] Зөөврийн компьютер дээр `python tools/sim_device.py --dry-run` ажиллаж байна
- [ ] Багийн Git санд эхний commit хийгдсэн, багш унших эрхтэй

Аль нэг нь ✘ бол лабораторийн өмнөх өдөр багшид хандана.
