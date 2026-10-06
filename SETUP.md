# SETUP — Лаб 1-ээс өмнө нэг удаа хийх бэлтгэл

Энэ заавраар **нэг удаа** бэлтгэсэн орчинг 8 лабораторийн ажил бүгд ашиглана. Үүнийг лабораторийн цагаар биш, **I–II долоо хоногийн бие даалтаар** гүйцэтгэнэ. Лаб 1-д ирэхээс өмнө бүх алхмыг дуусгаж, **Г хэсгийн хяналтын жагсаалтыг** бүгдийг ✔ болгосон байх ёстой.

| Хэсэг | Хаана | Юу хийх вэ | Хугацаа |
|---|---|---|---|
| **0** | — | Уншиж, өөрийн утгуудаа тэмдэглэх | 10 мин |
| **А** | 💻 Зөөврийн компьютер (үүл) | WSL 2 + Ubuntu, Git, VS Code, Docker Desktop, Raspberry Pi Imager → үүлний стек | 1.5–2 цаг |
| **Б** | 🥧 Raspberry Pi 3B (ирмэг) | microSD бичих, Docker Engine, swap, cgroup, ирмэгийн орчин | 1.5–2 цаг |
| **В** | 💻🥧 Хоёулаа | Гүүр холбож, мессеж дамжихыг шалгах | 15 мин |
| **Г** | 💻🥧 | Хяналтын жагсаалт | 10 мин |
| **Д** | — | Түгээмэл алдаа ба шийдэл | хэрэгтэй үед |

Нийт **3–4 цаг**, ихэнх нь татаж авах хугацаа — **хурдан интернэттэй газар** хий. Лаб 8-ын K3s server VM (А.8)-ийг Лаб 8-аас өмнө тусад нь бэлтгэнэ (+30 мин).

> 💡 **Алхмуудыг дарааллаар нь хий.** Алхам бүрийн төгсгөлд ✅ **Шалгах** гэсэн хэсэг бий. Тэнд бичсэн үр дүн гарахгүй бол **цааш бүү яв** — Д хэсгээс шалтгааныг хайж ол. Алдааг дараа нь засах нь хамаагүй хэцүү.

---

## 0. Эхлэхээс өмнө уншина уу

### 0.1 Командыг ХААНА бичихийг анхаар

Энэ курст **гурван өөр терминал** ашиглана. Код блок бүрийн дээр командыг аль терминалд бичихийг заасан:

| Тэмдэглэгээ | Хаана ажиллана | Хэрхэн нээх вэ | Prompt (мөрийн эхлэл) |
|---|---|---|---|
| **[💻 PowerShell]** | Windows | Start → `Terminal` (Windows 10-д `PowerShell`) | `PS C:\Users\bat>` |
| **[💻 PowerShell (Admin)]** | Windows, администраторын эрхтэй | Start → `Terminal` → **баруун товч** → **Run as administrator** → **Yes** | `PS C:\WINDOWS\system32>` |
| **[💻 Ubuntu]** | Зөөврийн компьютер доторх Linux (WSL) | Start → `Ubuntu` (эсвэл Terminal-ын `˅` товч → **Ubuntu**) | `bat@LAPTOP:~$` |
| **[🥧 Pi]** | Raspberry Pi дээр, SSH-ээр | Б.2-т заасан | `cnc302@pi-team07:~ $` |

> ⚠️ **Хамгийн түгээмэл алдаа:** командыг буруу терминалд бичих. Командыг бичихээсээ өмнө **prompt-ыг хар**.
>
> 💡 **Лабораторийн зааварт** 💻 гэж тэмдэглэсэн бүх командыг **[💻 Ubuntu]** терминалд бичнэ. Лабын заавар `make`, `mosquitto_sub`, `python3` зэрэг Linux командыг ашигладаг — тэдгээр нь Windows PowerShell-д байхгүй, харин Ubuntu (WSL) дотор шууд ажиллана. PowerShell-ийг зөвхөн энэ SETUP-д, Windows-ийн тохиргоонд л хэрэглэнэ.

> 💡 **macOS / Linux зөөврийн компьютертэй бол:** WSL-тэй холбоотой алхмуудыг (А.1.3, А.2-ын `.wslconfig`) алгас. [💻 PowerShell] ба [💻 Ubuntu] гэсэн бүх командыг өөрийн **Terminal**-д бич. Docker Desktop-ийн санах ойг **Settings → Resources → Advanced → Memory limit**-ээр тохируулна (А.2).

### 0.2 Командыг хэрхэн хуулах вэ

1. Код блокийн баруун дээд буланд байгаа **хуулах (copy)** товчийг дар — эсвэл хулганаар бүтэн мөрийг сонгож `Ctrl + C`.
2. Терминал дээр **баруун товч** дар (эсвэл `Ctrl + Shift + V`) — буулгана.
3. `Enter` дар.
4. Команд **дуусахыг хүлээ**: prompt дахин гарч ирсний дараа дараагийн командаа бич.

- `sudo` гэж эхэлсэн команд **нууц үг** асууна. Нууц үг бичихэд дэлгэцэнд **юу ч гарахгүй** (одоор ч харагдахгүй) — энэ хэвийн. Бичээд `Enter` дар.
- `#`-ээс хойшхи хэсэг бол **тайлбар** — бичих шаардлагагүй.
- Командыг зогсоох: `Ctrl + C`.

### 0.3 Өөрийн утгуудыг тэмдэглэ

Заавар дахь `<…>` хэсгийг өөрийн утгаар солино. **Хаалтыг (`< >`) хамт устгана.** Жишээ: `pi-team<NN>` → `pi-team07`.

| Хувьсагч | Утга | Жишээ | Хаанаас |
|---|---|---|---|
| `<NN>` | Багийн дугаар, **хоёр оронтой** | `07` | Багш |
| `<REPO_URL>` | Багийн Git сангийн хаяг | `https://github.com/…/cnc302-team07.git` | Багш |
| `<LAPTOP_IP>` | Зөөврийн компьютерийн LAN IP | `192.168.1.100` | А.5 |
| `<PI_IP>` | Pi-гийн IP хаяг | `192.168.1.57` | Б.2 |

Pi-гийн hostname нь `pi-team<NN>`, хэрэглэгч нь **`cnc302`**, ирмэгийн `DEVICE_ID` нь `pi3b-team<NN>` байна. Эдгээр нэрийг **өөрчлөхгүй** — лабын код ба `edge/agent/cnc302-edge-agent.service` яг эдгээр нэрийг хүлээнэ.

### 0.4 Тоног төхөөрөмжийн шаардлага

| Зүйл | Шаардлага |
|---|---|
| Зөөврийн компьютер | Windows 10 22H2 (build 19045) эсвэл Windows 11 23H2 (build 22631)+, 64-bit; **RAM ≥ 8 GB** (16 GB тав тухтай — Лаб 8); дискэнд **≥ 40 GB** сул зай |
| Raspberry Pi 3B | + **5 V / 2.5 A** тэжээлийн адаптер (утасны цэнэглэгч хангалтгүй) + **microSD 16 GB+** (A1/A2) + microSD уншигч |
| Сүлжээ | Зөөврийн компьютер ба Pi **нэг сүлжээнд**. Pi-г **кабелиар** холбох нь хамгийн найдвартай (А.5) |

---

## А. 💻 Зөөврийн компьютер дээр

### А.1 Програмууд суулгах

Суулгах дараалал **чухал**: WSL → Git → VS Code → Docker Desktop → Raspberry Pi Imager. Docker Desktop нь WSL 2 дээр ажилладаг тул WSL-ийг **эхэлж** суулгана.

| # | Програм | Юунд хэрэглэх вэ |
|---|---|---|
| А.1.3 | **WSL 2 + Ubuntu** | Windows доторх Linux. Лабын бүх 💻 команд энд ажиллана |
| А.1.4 | **Git for Windows** | Git-ийн нэвтрэлт (Credential Manager), VS Code-ийн Git |
| А.1.5 | **VS Code** | Код засах, Ubuntu (WSL) ба Pi (SSH) руу холбогдох |
| А.1.6 | **Docker Desktop** | Үүлний стек (EMQX, InfluxDB, Grafana, …) |
| А.1.7 | **Raspberry Pi Imager** | microSD карт бичих |
| А.1.9 | Ubuntu доторх хэрэгслүүд | `make`, `python3-venv`, `mosquitto-clients`, `git`, `curl` |

#### А.1.1 Windows-ийн хувилбар ба virtualization шалгах

**Алхам 1 — Windows-ийн хувилбар.** `Win + R` → `winver` гэж бичээд `Enter`.

✅ **Шалгах:** Нээгдсэн цонхонд **Version 22H2** (Windows 10) эсвэл **Version 23H2 / 24H2 / 25H2** (Windows 11) байна. Хуучин бол **Settings → Windows Update → Check for updates** → бүх шинэчлэлийг суулгаж, restart хий, дахин шалга.

> 💡 Windows **Home** хувилбар ч болно. Docker-ийн баримтаар Home нь зөвхөн *Linux контейнер* ажиллуулна — бидэнд яг тэр л хэрэгтэй.

**Алхам 2 — Virtualization.**

1. `Ctrl + Shift + Esc` → **Task Manager** нээгдэнэ.
2. Зүүн талаас **Performance** → **CPU** сонго.
3. Баруун доод хэсгээс **Virtualization**-ийг хай.

✅ **Шалгах:** `Virtualization: Enabled`.

❌ **Disabled** бол компьютерээ restart хийж, асах үед BIOS руу ор (DELL: `F2`; бусад: `F2`, `Del`, `F10` эсвэл `Esc`). **Intel Virtualization Technology (VT-x)** эсвэл AMD дээр **SVM Mode**-ийг хайж **Enabled** болго → **Save & Exit**. Олдохгүй бол багшид хандана.

#### А.1.2 `winget` ба Windows Terminal шалгах

`winget` бол Windows-ийн багц менежер: програмыг **албан ёсны эх сурвалжаас** нэг командаар татаж суулгана.

**[💻 PowerShell]**
```powershell
winget --version
```

✅ **Шалгах:** `v1.x.x` гэж хэвлэнэ.

❌ `winget is not recognized` гэвэл: **Microsoft Store** → `App Installer` гэж хайж → **Update** (эсвэл **Get**) → PowerShell-ээ хаагаад дахин нээ.

Windows 10 дээр **Windows Terminal** байхгүй бол суулга (Windows 11-д суулгаастай):

**[💻 PowerShell]**
```powershell
winget install --id Microsoft.WindowsTerminal -e
```

> 💡 `winget`-ийг **анх удаа** ажиллуулахад `Do you agree to all the source agreements terms? [Y] Yes [N] No` гэж асууна → `Y` дараад `Enter`. Суулгах явцад Windows **"Do you want to allow this app to make changes?"** гэж асуувал **Yes**.

#### А.1.3 WSL 2 ба Ubuntu суулгах

WSL (Windows Subsystem for Linux) нь Windows дотор жинхэнэ Linux ажиллуулна. Docker Desktop контейнерүүдээ үүн дотор ажиллуулдаг бөгөөд бид лабын командуудаа **Ubuntu** дотор бичнэ.

**Алхам 1 — суулгах.**

**[💻 PowerShell (Admin)]**
```powershell
wsl --install -d Ubuntu
```

Татаж суулгахад 5–10 мин болно. `The requested operation is successful. Changes will not be effective until the system is rebooted.` гэвэл **компьютерээ restart хий**.

> ❌ Явц `0.0%` дээр удаан зогсвол `Ctrl + C` дараад: `wsl --install --web-download -d Ubuntu`
>
> ❌ Команд суулгахын оронд тусламжийн текст хэвлэвэл WSL аль хэдийн суусан байна → `wsl --update` хийгээд дараа нь `wsl --install -d Ubuntu`.

**Алхам 2 — Ubuntu-гийн хэрэглэгч үүсгэх.** Restart хийсний дараа **Ubuntu** цонх автоматаар нээгдэнэ (нээгдэхгүй бол Start → `Ubuntu`). Хэдэн минут хүлээсний дараа:

```
Enter new UNIX username:
```
→ **жижиг латин үсгээр**, хоосон зайгүй нэр бич (жишээ: `bat`) → `Enter`.

```
New password:
Retype new password:
```
→ нууц үгээ хоёр удаа бич (**дэлгэцэнд харагдахгүй — хэвийн**). Энэ бол Ubuntu-гийн `sudo` нууц үг — **тэмдэглэж ав**.

✅ Prompt `bat@LAPTOP-XXXX:~$` болж өөрчлөгдвөл Ubuntu бэлэн.

**Алхам 3 — WSL-ийн хувилбар шалгах.**

**[💻 PowerShell]**
```powershell
wsl --update
wsl --version
wsl --list --verbose
```

✅ **Шалгах:**
- `wsl --version`-ийн эхний мөр: `WSL version: 2.x.x` — **2.1.5-аас бага биш** (Docker Desktop-ийн шаардлага).
- `wsl --list --verbose`: `Ubuntu` мөрийн **VERSION** баганад `2`, нэрийн өмнө `*` (анхдагч distribution).

❌ VERSION `1` бол: `wsl --set-version Ubuntu 2`. `*` өөр distribution дээр байвал: `wsl --set-default Ubuntu`.

#### А.1.4 Git for Windows

**[💻 PowerShell]**
```powershell
winget install --id Git.Git -e
```

Суусны дараа **PowerShell-ээ хаагаад шинээр нээ** (шинэ програм PATH-д нэмэгдэнэ).

**[💻 PowerShell]**
```powershell
git --version
git credential-manager --version
```

✅ **Шалгах:** хоёулаа хувилбарын дугаар хэвлэнэ (`git version 2.5x…`, `2.x.x…`).

> 💡 Git-ийг Ubuntu дотор ч ашиглана (А.1.9). Windows-ийн Git нь Ubuntu-д GitHub-ын нэвтрэлтийг хадгалах **Git Credential Manager**-ийг өгдөг (А.3).

#### А.1.5 VS Code ба өргөтгөлүүд

**[💻 PowerShell]**
```powershell
winget install --id Microsoft.VisualStudioCode -e
```

PowerShell-ээ **хаагаад шинээр нээ**, дараа нь өргөтгөлүүдийг суулга (мөр бүрийг тус тусад нь, эсвэл бүгдийг нэг дор буулгаж болно):

**[💻 PowerShell]**
```powershell
code --install-extension ms-vscode-remote.remote-wsl
code --install-extension ms-vscode-remote.remote-ssh
code --install-extension ms-python.python
code --install-extension ms-azuretools.vscode-containers
code --install-extension redhat.vscode-yaml
```

| Өргөтгөл | Юунд |
|---|---|
| **WSL** | Ubuntu доторх файлыг VS Code-оор нээх (`code .`) |
| **Remote - SSH** | Pi дээрх файлыг шууд засах (В.3) |
| **Python** | Python код |
| **Container Tools** | Контейнер, Compose файл |
| **YAML** | `docker-compose.yml`-ийн алдааг илрүүлэх |

✅ **Шалгах:** `code --list-extensions` → дээрх таван ID жагсаалтад байна.

#### А.1.6 Docker Desktop

**Алхам 1 — суулгах.**

**[💻 PowerShell]**
```powershell
winget install --id Docker.DockerDesktop -e
```

Installer-ийн цонх нээгдвэл:

1. **Configuration** хуудсанд **Use WSL 2 instead of Hyper-V** чагттай байгааг шалга (анхдагчаар чагттай).
2. **OK** дар → суулгаж дуусахыг хүлээ (3–5 мин).
3. **Close** (эсвэл **Close and log out**) гарвал дар. Log out хийвэл дахин нэвтэр.

> 💡 `winget` ажиллахгүй бол: https://docs.docker.com/desktop/setup/install/windows-install/ → **Docker Desktop for Windows – x86_64** товчоор `Docker Desktop Installer.exe` татаж, давхар товшоод дээрх 1–3-ыг хий.

**Алхам 2 — анх асаах.**

1. Start → `Docker Desktop` → нээ.
2. **Docker Subscription Service Agreement** гарна → **Accept**. (Зөвшөөрөхгүй бол Docker Desktop ажиллахгүй. Боловсролын зорилгоор үнэгүй.)
3. Нэвтрэх (Sign in) эсвэл судалгааны цонх гарвал **Skip** / **Continue without signing in** дар.
4. Цонхны **зүүн доод буланд** `Engine running` (ногоон) гэж гартал хүлээ — анх удаа 1–3 мин.

**Алхам 3 — WSL-тэй холбох.** Docker Desktop-ийн баруун дээд буланд **⚙ (Settings)**:

1. **General** → **Use the WSL 2 based engine** чагттай байгааг шалга.
2. **Resources** → **WSL integration** →
   - **Enable integration with my default WSL distro** — чагттай,
   - доорх жагсаалтад **Ubuntu**-гийн шилжүүлэгч — **асаалттай** (цэнхэр).
3. **Apply & restart** дар.

**Алхам 4 — шалгах (хоёр терминалаас).**

**[💻 PowerShell]**
```powershell
docker version
docker compose version
docker run --rm hello-world
```

**[💻 Ubuntu]**
```bash
docker version
docker compose version
docker run --rm hello-world
```

✅ **Шалгах (хоёр терминал дээр хоёуланд нь):**
- `docker version` нь **Client:** ба **Server:** гэсэн **хоёр** хэсэг хэвлэнэ.
- `docker compose version` → `Docker Compose version v2.x.x`.
- `hello-world` → `Hello from Docker!` гэсэн мөр гарна.

❌ `error during connect` / `Cannot connect to the Docker daemon` → Docker Desktop ажиллаагүй байна: Алхам 2-ын 4-р зүйлийг шалга.
❌ Ubuntu-д `docker: command not found` эсвэл `The command 'docker' could not be found in this WSL 2 distro` → Алхам 3-ын **WSL integration** асаагүй байна.

> 💡 **Docker Desktop-ийг лаб бүрийн өмнө асаа.** Компьютер асах бүрт автоматаар асаах бол: **Settings → General → Start Docker Desktop when you sign in to your computer**.

#### А.1.7 Raspberry Pi Imager

**[💻 PowerShell]**
```powershell
winget install --id RaspberryPiFoundation.RaspberryPiImager -e
```

✅ **Шалгах:** Start цэсэнд **Raspberry Pi Imager** гарч ирнэ. Хувилбар нь **2.0 ба түүнээс шинэ** байх ёстой (Б.1-ийн дэлгэцүүд энэ хувилбарынх).

> 💡 Гараар: https://www.raspberrypi.com/software/ → **Download for Windows**.

#### А.1.8 MQTT Explorer (сонголтот)

Брокер дахь сэдвийн модыг график хэлбэрээр харуулна. Заавал биш — `mosquitto_sub` хангалттай.

**[💻 PowerShell]**
```powershell
winget install --id thomasnordquist.MQTT-Explorer -e
```

#### А.1.9 Ubuntu доторх хэрэгслүүд

**[💻 Ubuntu]**
```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y git make curl python3-venv python3-pip mosquitto-clients
```

Эхний команд Ubuntu-гийн нууц үгийг (А.1.3, Алхам 2) асууна.

✅ **Шалгах:**

**[💻 Ubuntu]**
```bash
git --version; make --version | head -1; python3 --version; mosquitto_sub --help | head -1
```

Дөрвөн мөр хувилбарын мэдээлэл хэвлэнэ (`python3` нь **3.10+**).

---

### А.2 Docker Desktop-ийн санах ой (ЗААВАЛ)

Docker Desktop-ийн баримтаар Linux VM-д анхдагчаар **хост компьютерийн санах ойн 50%**-ийг өгдөг. Бидэнд **6 GB** хэрэгтэй (Лаб 8-д Ollama). Тохируулах газар нь backend-ээс хамаарна:

- **Windows + WSL 2 backend (бидний сонголт):** Docker Desktop-ийн **Resources** хэсэгт Memory гулсуур **байхгүй** — санах ойг WSL 2-ын VM-д `%UserProfile%\.wslconfig` файлаар өгнө (доорх алхмууд).
- **macOS, Linux, Windows Hyper-V backend:** **Settings → Resources → Advanced → Memory limit → 6 GB** (16 GB-тай бол 8 GB) → *Apply & restart*.

**Алхам 1 — файл нээх.**

**[💻 PowerShell]**
```powershell
notepad "$env:USERPROFILE\.wslconfig"
```

`Cannot find the .wslconfig file. Do you want to create a new file?` гэж асуувал **Yes**.

**Алхам 2 — дараах хоёр мөрийг бичээд хадгал** (`Ctrl + S`), Notepad-ийг хаа:

```ini
[wsl2]
memory=6GB
```

| Компьютерийн RAM | `memory=` |
|---|---|
| 8 GB | `6GB` (Лаб 8-д Chrome ба бусад програмаа хаана) |
| 16 GB ба түүнээс их | `8GB` |

> ⚠️ Файлын нэр яг `.wslconfig` байх ёстой — **`.wslconfig.txt` БИШ**. Шалгах: `Get-ChildItem $env:USERPROFILE\.wslconfig` → алдаагүй гарвал зөв.

**Алхам 3 — WSL-ийг дахин эхлүүлэх.**

1. Docker Desktop-ийг хаа: taskbar-ын баруун доод талын **халимны дүрс** дээр баруун товч → **Quit Docker Desktop**.
2. Бүх Ubuntu цонхоо хаа.
3. **[💻 PowerShell]** `wsl --shutdown`
4. 10 секунд хүлээгээд Docker Desktop-ийг дахин нээ → `Engine running` болтол хүлээ.

✅ **Шалгах:**

**[💻 Ubuntu]**
```bash
docker info --format '{{.MemTotal}}' | awk '{printf "Docker-т %.1f GB\n", $1/1024/1024/1024}'
```

`Docker-т 5.8 GB` орчим (6GB тавьсан бол 5.7–6.0) гарна. Хэвээр 50% бол файлын нэр эсвэл байршил буруу (Алхам 2-ын ⚠️). **4 GB-аас бага бол Лаб 8-д `ai` профайл ажиллахгүй.**

> Албан ёсны баримт: [Docker Desktop — Settings (Resources)](https://docs.docker.com/desktop/settings-and-maintenance/settings/) · [WSL — .wslconfig](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)

---

### А.3 Сангаа татах ба Python орчин

**Алхам 1 — Git тохируулах** (нэг удаа):

**[💻 Ubuntu]**
```bash
git config --global user.name "Овог Нэр"
git config --global user.email "таны@имэйл.mn"
git config --global core.autocrlf input
git config --global credential.helper "/mnt/c/Program\ Files/Git/mingw64/bin/git-credential-manager.exe"
```

- `core.autocrlf input` — мөрийн төгсгөлийг Linux-ийн (LF) хэвээр үлдээнэ. Үгүй бол `.sh` файлд CRLF орж контейнерт `/bin/sh^M: bad interpreter` алдаа гарна.
- `credential.helper` — GitHub-ын нэвтрэлтийг Windows-ийн Git Credential Manager-т хадгална: `git clone`/`git push` анх удаа **хөтөч нээж** нэвтрүүлнэ, дараа нь дахин асуухгүй.

**Алхам 2 — сангаа Ubuntu-гийн гэрийн хавтаст clone хийх.**

> ⚠️ Сангаа **Ubuntu дотор** (`~/cnc302`) хадгална — `/mnt/c/…`, **OneDrive**, **Desktop**, **Documents**-д БИШ. Docker-ийн WSL-ийн зөвлөмжөөр Linux файлын системд байгаа файл контейнерт хамаагүй хурдан харагдана; OneDrive нь `.git`-ийг эвддэг.

**[💻 Ubuntu]**
```bash
cd ~
git clone <REPO_URL> cnc302
cd ~/cnc302
ls
```

✅ **Шалгах:** `lab01 … lab08  stack  edge  tools  docs  README.md  SETUP.md` харагдана.

> 💡 Сангаа VS Code-оор нээх: `cd ~/cnc302 && code .` — VS Code нээгдэж, зүүн доод буланд **WSL: Ubuntu** гэж харагдана. Windows-ийн File Explorer-оос: хаягийн мөрөнд `\\wsl$\Ubuntu\home\<ubuntu-нэр>\cnc302`.

**Алхам 3 — Python-ийн virtual environment.**

**[💻 Ubuntu]**
```bash
cd ~/cnc302
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r tools/requirements.txt
```

✅ Prompt-ын эхэнд `(.venv)` гарна. Шинэ Ubuntu цонх нээх бүрт **`cd ~/cnc302 && source .venv/bin/activate`**-ийг дахин бичнэ.

**Алхам 4 — шалгах.**

**[💻 Ubuntu]**
```bash
python tools/sim_device.py --dry-run --devices 2 --count 3
```

✅ Брокергүйгээр **6 мессежийн JSON** хэвлэгдэнэ. Хэвлэгдэхгүй бол цааш явахгүй.

---

### А.4 Үүлний стекийг татаж, асаах

**Алхам 1 — нууц утгын файл үүсгэх.**

**[💻 Ubuntu]**
```bash
cd ~/cnc302/stack
cp .env.example .env
nano .env
```

`nano` засварлагч нээгдэнэ. Сумаар зөөж дараах **гурван утгыг** өөрийнхөөрөө соль:

| Мөр | Юу бичих |
|---|---|
| `EMQX_COOKIE=` | дурын урт үг (жишээ: `team07-cookie-x8k2`) |
| `EMQX_DASHBOARD_PASSWORD=` | EMQX самбарын нууц үг — **тэмдэглэж ав** |
| `GRAFANA_PASSWORD=` | Grafana-гийн нууц үг — **тэмдэглэж ав** |

Бусад мөрийг (жишээ нь хоосон `EMQX_API_KEY=`) **хэвээр нь** үлдээ — тэдгээрийг Лаб 2-т бөглөнө.

Хадгалах: `Ctrl + O` → `Enter`. Гарах: `Ctrl + X`.

> ⚠️ Нууц үгийг **стекийг анх асаахаас өмнө** соль. EMQX ба Grafana нууц үгээ зөвхөн **анх асахдаа** `.env`-ээс уншина; дараа нь `.env`-ийг сольсон ч өөрчлөгдөхгүй.

**Алхам 2 — image-уудыг татах** (анх удаа хэдэн GB, **10–30 мин**):

**[💻 Ubuntu]**
```bash
docker compose --profile core pull --ignore-buildable
```

`--ignore-buildable` — манай `registry` image Docker Hub-д байхгүй, дараагийн алхамд **локалд барина**; энэ туг түүнийг татах гэж оролдохгүй болгоно.

**Алхам 3 — асаах.**

**[💻 Ubuntu]**
```bash
make up
```

Анх удаа `registry`-г барина (2–5 мин). Төгсгөлд `Pi-гийн edge/.env файлд бичих утга:` гэсэн жагсаалт хэвлэгдэнэ — А.5-д хэрэглэнэ.

**Алхам 4 — шалгах.** 1 минут хүлээгээд:

**[💻 Ubuntu]**
```bash
make status
make health
```

✅ **Шалгах:**
- `make status`-ын **STATUS** баганад бүх контейнер `Up` эсвэл `Up (healthy)`. `starting` / `health: starting` бол 1 мин хүлээгээд дахин ажиллуул.
- `make health` дөрвөн мөр **`200`** хэвлэнэ:
  ```
  EMQX      200
  InfluxDB  200
  Grafana   200
  Registry  200
  ```

Хөтчөөр шалгах:

| Хаяг | Нэвтрэх |
|---|---|
| http://localhost:18083 | EMQX самбар: `admin` / `EMQX_DASHBOARD_PASSWORD` |
| http://localhost:3000 | Grafana: `admin` / `GRAFANA_PASSWORD` |

> 💡 Стекийг зогсоох (өгөгдөл устахгүй): `make down`. Дахин асаах: `make up`. **`make clean` бүх өгөгдлийг устгана** — хэрэглэхээсээ өмнө бод.

---

### А.5 LAN IP хаягаа олох (ЧУХАЛ)

Pi нь зөөврийн компьютерт **LAN IP**-ээр холбогдоно — `localhost` БИШ (Pi дээр `localhost` гэдэг нь Pi өөрөө).

**[💻 PowerShell]**
```powershell
ipconfig
```

Гаралтаас **Wireless LAN adapter Wi-Fi** (кабелиар бол **Ethernet adapter Ethernet**) хэсгийг олж, **IPv4 Address** мөрийн утгыг ав. Энэ бол `<LAPTOP_IP>` — **тэмдэглэ**.

> ⚠️ `vEthernet (WSL…)` эсвэл `vEthernet (Default Switch)` хэсгийн хаягийг БҮҮ ав — тэр нь Windows доторх **дотоод** сүлжээ, Pi түүнийг харахгүй. Ubuntu дотор `ip addr`-оор гарах `172.x.x.x` хаяг ч мөн адил **буруу**.
>
> 💡 Ubuntu-гийн `make ip` (`make up`-ын төгсгөлд хэвлэгддэг) WSL дотор Windows-ийн `ipconfig`-ийн IPv4 мөрүүдийг харуулна — тэндээс мөн Wi-Fi/Ethernet адаптерийнхийг сонго.

**Сүлжээний профайлыг Private болгох.** **Settings → Network & internet → Wi-Fi** (эсвэл **Ethernet**) → холбогдсон сүлжээний нэр → **Network profile type** → **Private network**. Public байвал Windows Firewall Pi-гаас ирэх холболтыг хаана (А.6).

> **Сүлжээний урхи:**
> - Хамгийн найдвартай нь **хоёуланг нь нэг router/switch-д кабелиар** холбох.
> - Pi 3B-ийн Wi-Fi нь **зөвхөн 2.4 GHz**. 5 GHz сүлжээ Imager-т харагдах боловч Pi холбогдохгүй.
> - Их сургуулийн нийтийн Wi-Fi ихэвчлэн төхөөрөмжүүдийг хооронд нь **тусгаарладаг** (client isolation) тул Pi зөөврийн компьютерээ "харахгүй". Лабораторийн router эсвэл утасныхаа **2.4 GHz hotspot**-ыг ашигла.
> - Зөөврийн компьютер Wi-Fi-аар, Pi кабелиар холбогдсон бол өөр дэд сүлжээнд (subnet) байж болно — `<LAPTOP_IP>` ба `<PI_IP>`-ийн эхний гурван тоо ижил эсэхийг шалга.
> - IP **өөрчлөгдөж болно** (өөр сүлжээ, router restart). Лаб бүрийн эхэнд `ipconfig`-оор шалга.

---

### А.6 Галт хана (Windows)

Windows Defender Firewall гаднаас ирэх холболтыг анхдагчаар хаадаг. Pi-гаас ирэх портуудыг нээнэ: **1883** (MQTT, гүүр), **8883** (MQTT/TLS, Лаб 2), **8090** (registry/OTA, Лаб 2), **8181** (InfluxDB), **3000** (Grafana).

**[💻 PowerShell (Admin)]** — доорх **хоёр мөрийг бүтнээр нь нэг дор** хуулж буулга (эхний мөрийн төгсгөлийн `` ` `` тэмдэг нь "команд дараагийн мөрөнд үргэлжилнэ" гэсэн утгатай):
```powershell
New-NetFirewallRule -DisplayName "CNC302 cloud" -Direction Inbound `
  -Protocol TCP -LocalPort 1883,8883,8090,8181,3000 -Action Allow -Profile Private
```

✅ **Шалгах:**

**[💻 PowerShell]**
```powershell
Get-NetFirewallRule -DisplayName "CNC302 cloud" | Format-Table DisplayName, Enabled, Profile, Action
```

`CNC302 cloud  True  Private  Allow` гарна.

> Зөвхөн **Private** профайлд нээ (А.5). Нийтийн сүлжээнд задгай MQTT брокер орхиж болохгүй.
>
> 💡 Docker Desktop эсвэл өөр програм **"Windows Defender Firewall has blocked some features"** цонх гаргавал **Private networks**-ийг чагтлаад **Allow access** дар.
>
> Албан ёсны баримт: [New-NetFirewallRule](https://learn.microsoft.com/en-us/powershell/module/netsecurity/new-netfirewallrule)

---

### А.7 SSH түлхүүр үүсгэх

Pi руу **нууц үггүй, түлхүүрээр** нэвтэрнэ. Түлхүүрийг **Windows** талд үүсгэнэ — PowerShell-ийн `ssh` болон VS Code хоёулаа үүнийг ашиглана.

**Алхам 1 — түлхүүр үүсгэх.**

**[💻 PowerShell]**
```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.ssh" | Out-Null
ssh-keygen -t ed25519 -C "таны@имэйл.mn" -f "$env:USERPROFILE\.ssh\cnc302"
```

`Enter passphrase` гэж асуувал хоосон орхиж **Enter**, дахин **Enter**.

✅ `Your identification has been saved in C:\Users\…\.ssh\cnc302` гэж гарна. Хоёр файл үүснэ:

| Файл | Юу вэ | |
|---|---|---|
| `cnc302` | **нууц** түлхүүр | ⛔ **Хэнд ч бүү өг, Git-д хэзээ ч бүү оруул** |
| `cnc302.pub` | **нийтийн** түлхүүр | Pi-д өгнө (Б.1) |

**Алхам 2 — нийтийн түлхүүрийг харах.** Б.1-д хуулж буулгана:

**[💻 PowerShell]**
```powershell
Get-Content "$env:USERPROFILE\.ssh\cnc302.pub"
```

`ssh-ed25519 AAAAC3Nza… таны@имэйл.mn` гэсэн **нэг урт мөр** гарна.

**Алхам 3 — `ssh pi` товчлол үүсгэх.** Доорх блокийн `<NN>`-ийг багийн дугаараар **сольсны дараа** бүтнээр нь буулга:

**[💻 PowerShell]**
```powershell
Add-Content -Encoding ascii "$env:USERPROFILE\.ssh\config" @"

Host pi
    HostName pi-team<NN>.local
    User cnc302
    IdentityFile ~/.ssh/cnc302
"@
```

Одооноос `ssh pi` гэж бичихэд `ssh -i ~/.ssh/cnc302 cnc302@pi-team<NN>.local`-тай ижил ажиллана. VS Code ч энэ файлыг уншина (В.3).

✅ **Шалгах:** `Get-Content "$env:USERPROFILE\.ssh\config"` → `HostName pi-team07.local` гэх мэт **өөрийн дугаартай** мөр харагдана (`<NN>` үлдсэн бол файлыг `notepad "$env:USERPROFILE\.ssh\config"`-оор засна).

---

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

### Б.1 microSD карт бичих (Raspberry Pi Imager)

> ⚠️ Бичихэд картын **бүх өгөгдөл устна**. Компьютерийн өөр диск эсвэл USB flash-ийг андуурч сонгохгүйн тулд **бусад USB төхөөрөмжөө салга**.

1. microSD картаа уншигчаар зөөврийн компьютерт залга.
   > ⚠️ Windows **"You need to format the disk in drive X: before you can use it"** гэж асуувал **Cancel** дар. Format хийх ШААРДЛАГАГҮЙ.
2. **Raspberry Pi Imager**-ийг нээ (Windows зөвшөөрөл асуувал **Yes**).
3. **Device** → **Raspberry Pi 3** → **Next**.
4. **OS** → **Raspberry Pi OS (other)** → **Raspberry Pi OS Lite (64-bit)** → **Next**.

   > ⚠️ **64-bit заавал.** Манай бүх image ба Python wheel (`ai-edge-litert` г.м.) arm64-д зориулагдсан. Docker Engine v29-өөс эхлэн Raspberry Pi OS 32-bit (armhf)-д шинэ багц гаргахаа больсон.
   >
   > ⚠️ **Lite заавал.** Lite бол дэлгэцгүй, *"command-line-only"* хувилбар — ширээний орчин 1 GB-д хэт үнэтэй. Одоогийн хувилбар нь **Debian Trixie** дээр суурилсан (өмнөх нь Bookworm).

5. **Storage** → **microSD картаа** сонго. **Хэмжээг нь шалга** (16 GB карт бол ~15 GB гэж харагдана) → **Next**.
6. **Customisation** (OS тохируулга) — хуудас бүрт доорх утгыг оруулаад **Next**:

   | Хуудас | Талбар | Утга |
   |---|---|---|
   | **Hostname** | Hostname | `pi-team<NN>` (жишээ: `pi-team07`) |
   | **Localisation** | Capital city | **Ulaanbaatar (Mongolia)** |
   | | Time zone | `Asia/Ulaanbaatar` (автоматаар бөглөгдөнө) |
   | | Keyboard layout | `us` |
   | **User** | Username | **`cnc302`** (өөр нэр бүү ашигла) |
   | | Password | Өөрийн нууц үг — **тэмдэглэж ав** (`sudo`-д хэрэгтэй) |
   | **Wi-Fi** | | **Кабель** ашиглах бол алгас (**Skip**). Wi-Fi бол: SSID ба нууц үг (**2.4 GHz**, том/жижиг үсгийг яг зөв) |
   | **Remote access** | Enable SSH | **асаана** |
   | | Authentication | **Use public key authentication** |
   | | Public key | А.7, Алхам 2-т гарсан **бүтэн мөрийг** (`ssh-ed25519 AAAA… таны@имэйл.mn`) буулга |
   | **Raspberry Pi Connect** | | **Унтраалттай** үлдээ |

   > ⚠️ Hostname **баг бүрт өөр** байх ёстой. Ижил нэртэй хоёр Pi нэг сүлжээнд байвал хооронд нь ялгах боломжгүй.
   >
   > 💡 Imager-ийн хувилбараас хамаарч хуудасны нэр бага зэрэг өөр байж болно — утга нь адилхан.

7. **Write** → анхааруулга гарвал **I understand, erase and write** (эсвэл **Yes**) дар. Windows-ийн администраторын зөвшөөрөл асуувал **Yes**.
8. Бичих (**Writing**) ба баталгаажуулах (**Verifying**) явц дуусахыг хүлээ (5–15 мин). **Write complete!** гарвал картаа салга.

> Албан ёсны баримт: [Getting started — Install using Imager](https://www.raspberrypi.com/documentation/computers/getting-started.html) · [Raspberry Pi OS](https://www.raspberrypi.com/documentation/computers/os.html) · [A new Raspberry Pi Imager (2.0)](https://www.raspberrypi.com/news/a-new-raspberry-pi-imager/)

### Б.2 Анх асаах, SSH-ээр холбогдох, шинэчлэх

**Алхам 1 — асаах.**

1. microSD картаа Pi-д хий (контактаараа дээш биш, **доош** — PCB тал руу).
2. Ethernet кабелиа зөөврийн компьютертэй **нэг router/switch**-д залга.
3. Тэжээлээ **хамгийн сүүлд** залга. Улаан гэрэл асаж, ногоон гэрэл анивчина.
4. **3–5 минут хүлээ.** Pi анх асахдаа файлын системээ өргөтгөж, өөрөө нэг-хоёр удаа restart хийнэ.

**Алхам 2 — Pi-г сүлжээнээс олох.**

**[💻 PowerShell]**
```powershell
ping -4 pi-team<NN>.local
```

✅ `Reply from 192.168.x.x: bytes=32 time=…` гарна. Тэр хаяг бол `<PI_IP>` — **тэмдэглэ**.

❌ `Ping request could not find host`: (а) дахиад 2 мин хүлээгээд оролд; (б) router-ийн удирдлагын хуудаснаас **connected devices / DHCP clients** жагсаалтад `pi-team<NN>`-ийг хайж IP-г ол; (в) Д хэсэг.

**Алхам 3 — SSH-ээр холбогдох.**

**[💻 PowerShell]**
```powershell
ssh pi
```

(`.local` ажиллахгүй бол: `ssh -i "$env:USERPROFILE\.ssh\cnc302" cnc302@<PI_IP>`.)

Анх удаа:
```
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```
→ `yes` гэж **бүтнээр** бичээд `Enter`.

✅ Нууц үг асуулгүйгээр prompt `cnc302@pi-team07:~ $` болж өөрчлөгдөнө. Одооноос **[🥧 Pi]** командыг **энэ цонхонд** бичнэ.

❌ `Permission denied (publickey)` → Д хэсэг.

**Алхам 4 — системийг шинэчлэх ба хэрэгслүүд суулгах** (10–20 мин):

**[🥧 Pi]**
```bash
sudo apt update
sudo apt full-upgrade -y
sudo apt install -y git curl jq htop iotop stress-ng mosquitto-clients \
                    netcat-openbsd python3-venv python3-dev
sudo reboot
```

`sudo` анх удаа Б.1-д тавьсан **Pi-гийн нууц үгийг** асууна. Сүүлийн мөрийн төгсгөлийн `\` нь "команд дараагийн мөрөнд үргэлжилнэ" гэсэн утгатай — хоёр мөрийг **хамт** хуул.

`reboot` хийхэд SSH тасарна (`Connection to … closed`) — энэ хэвийн. **1–2 мин хүлээгээд** `ssh pi`-ээр дахин холбогд.

**Алхам 5 — үндсэн шалгалт.**

**[🥧 Pi]**
```bash
uname -m
dpkg --print-architecture
. /etc/os-release && echo "$PRETTY_NAME"
free -h
vcgencmd get_throttled
```

✅ **Хүлээгдэх үр дүн:**

| Команд | Байх ёстой | Өөр бол |
|---|---|---|
| `uname -m` | `aarch64` | `armv7l` → 32-bit OS бичсэн байна → Б.1-ийг дахин хий |
| `dpkg --print-architecture` | `arm64` | дээрхтэй адил |
| `PRETTY_NAME` | `Debian GNU/Linux 13 (trixie)` (эсвэл `12 (bookworm)`) | — |
| `free -h` → Mem total | ≈ `900Mi` | — |
| `get_throttled` | `throttled=0x0` | Тэжээл сул → Б.0, Д хэсэг |

### Б.3 GPU-гийн санах ой (`gpu_mem`) — хэмжиж шийднэ

Raspberry Pi-гийн баримтаар 1 GB-тай загварт `gpu_mem`-ийн **анхдагч утга 76** MiB. Гэхдээ баримт `gpu_mem`-ийг **legacy** тохиргоонд ангилж, *Raspberry Pi OS Bookworm болон түүнээс хойшхи хувилбарт ажиллахгүй, албан ёсоор дэмжигдэхгүй* гэж тэмдэглэсэн. Тиймээс «N MiB хэмнэнэ» гэж амлахгүй — **өмнө ба дараа нь хэмжинэ**.

**Алхам 1 — өмнөх утгыг хэмжих.**

**[🥧 Pi]**
```bash
grep MemTotal /proc/meminfo
vcgencmd get_mem gpu
```

Хоёр утгыг (жишээ: `MemTotal: 925…kB`, `gpu=76M`) **тэмдэглэ** — (1).

**Алхам 2 — тохиргоо нэмж, дахин ачаалах.**

**[🥧 Pi]**
```bash
echo 'gpu_mem=16' | sudo tee -a /boot/firmware/config.txt
sudo reboot
```

**Алхам 3 — дахин холбогдоод** (`ssh pi`) **хэмжих.**

**[🥧 Pi]**
```bash
grep MemTotal /proc/meminfo
vcgencmd get_mem gpu
```

Утгыг **тэмдэглэ** — (2). (1) ба (2)-ын зөрүүг Лаб 1-ийн хүснэгтэд бич. Зөрүүгүй бол энэ мөр таны OS дээр нөлөөгүй гэсэн үг — буруу биш, **хэмжилт**.

> Албан ёсны баримт: [Legacy config.txt — gpu_mem](https://www.raspberrypi.com/documentation/computers/legacy_config_txt.html#gpu_mem)

### Б.4 Docker Engine суулгах

Pi дээр Docker **Desktop** биш, **Docker Engine** суулгана. 64-бит Raspberry Pi OS нь Debian-д суурилсан тул Docker-ийн **Debian** зааврыг (`apt` repository) дагана. `get.docker.com` convenience script-ийг Docker өөрөө *зөвхөн туршилт ба хөгжүүлэлтийн орчинд* зөвлөдөг тул бид ашиглахгүй.

**Алхам 1 — зөрчилдөх албан бус багцыг устгах.** Шинэ систем дээр эдгээр байхгүй тул `no packages found` эсвэл `0 to remove` гарна — **энэ хэвийн**.

**[🥧 Pi]**
```bash
sudo apt remove $(dpkg --get-selections docker.io docker-compose docker-doc docker-buildx podman-docker containerd runc | cut -f1)
```

**Алхам 2 — Docker-ийн GPG түлхүүр нэмэх** (`apt` Docker-ийн багцыг жинхэнэ эсэхийг үүгээр шалгана):

**[🥧 Pi]**
```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

✅ **Шалгах:** `ls -l /etc/apt/keyrings/docker.asc` → файл байна (хэмжээ ~3.8 KB).

**Алхам 3 — Docker-ийн repository нэмэх.** Доорх блокийг `sudo tee`-ээс `EOF` хүртэл **бүтнээр нь НЭГ ДОР** хуулж буулга:

**[🥧 Pi]**
```bash
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```

✅ **Шалгах:** терминал файлын агуулгыг хэвлэнэ. Тэнд **`Suites: trixie`** (эсвэл `bookworm`) ба **`Architectures: arm64`** байх ёстой. Хоосон бол Алхам 3-ыг дахин хий.

**Алхам 4 — суулгах.**

**[🥧 Pi]**
```bash
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

✅ `sudo apt update`-ийн гаралтад `https://download.docker.com/linux/debian trixie InRelease` мөр харагдана. Суулгалт 3–5 мин.

**Алхам 5 — `sudo`-гүй ажиллуулах эрх өгөх.**

**[🥧 Pi]**
```bash
sudo usermod -aG docker $USER
exit
```

> ⚠️ `exit` хийж SSH-ээс **заавал гараад**, `ssh pi`-ээр **дахин холбогд**. Бүлгийн эрх зөвхөн шинэ session-д хүчинтэй болно.
>
> ⚠ `docker` бүлэгт орсон хэрэглэгч root-той дүйцэх эрхтэй болдог (Docker-ийн post-install баримт) — Pi-гийн `cnc302` хэрэглэгчийн нууц үгийг хамгаал.

**Алхам 6 — шалгах.**

**[🥧 Pi]**
```bash
docker --version
docker compose version
docker run --rm hello-world
systemctl is-enabled docker
```

✅ **Хүлээгдэх үр дүн:**
- `Docker version 2x.x.x` ба `Docker Compose version v2.x.x` (**v2.20+**),
- `Hello from Docker!`,
- `enabled` (Pi асах бүрт Docker автоматаар асна).

❌ `permission denied while trying to connect to the Docker daemon socket` → Алхам 5-ын дараа SSH-ээс гараагүй байна.

**Алхам 7 — Docker-ийн лог microSD-г элээхээс сэргийлэх.** Блокийг **бүтнээр нь** буулга (`log-opts`-ийн утгууд **мөр** — хашилтанд — байх ёстой):

**[🥧 Pi]**
```bash
sudo tee /etc/docker/daemon.json > /dev/null <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "5m", "max-file": "2" }
}
EOF
sudo systemctl restart docker
```

✅ **Шалгах:** `docker info --format '{{.LoggingDriver}}'` → `json-file`. Энэ тохиргоо зөвхөн **шинээр үүсэх** контейнерт үйлчилнэ.

❌ `systemctl restart docker` алдаа гаргавал JSON-д алдаа байна: `sudo nano /etc/docker/daemon.json`-оор дээрх блоктой тулгаж засна.

> Албан ёсны баримт: [Install Docker Engine on Debian](https://docs.docker.com/engine/install/debian/) · [Linux post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/) · [JSON File logging driver](https://docs.docker.com/engine/logging/drivers/json-file/)

### Б.5 Солих санах ой (swap) ба cgroup (ЗААВАЛ)

#### Swap

1 GB RAM дээр swap нь Лаб 4–8-д OOM-оос хамгаалах **аюулгүйн сүлжээ**. Курсын бүх заавар **2 GiB** swap гэж тооцсон. Raspberry Pi OS-ийн хувилбараас хамаарч swap-ыг удирдах хэрэгсэл өөр байдаг тул **эхлээд аль нь болохыг** тодорхойлно.

**Алхам 1 — одоогийн байдал.**

**[🥧 Pi]**
```bash
swapon --show; free -h
test -e /etc/rpi/swap.conf && echo "rpi-swap" || echo "rpi-swap алга"
systemctl is-enabled dphys-swapfile 2>/dev/null
```

| Хоёр дахь мөрийн гаралт | Аль замаар явах |
|---|---|
| `rpi-swap` | **Алхам 2а** (шинэ Trixie image — ихэнх тохиолдол) |
| `rpi-swap алга` ба дараа нь `enabled` | **Алхам 2б** (хуучин Bookworm image) |

**Алхам 2а — `rpi-swap` байгаа бол.** Raspberry Pi-гийн `rpi-swap` багц `dphys-swapfile`-ийг орлох зорилготой; анхдагч `Mechanism=auto` нь одоогоор **zram+file** (шахсан RAM swap + ховор бичигддэг файл), zram-ын хэмжээ анхдагчаар RAM-тай тэнцүү (2048 MiB-ээр хязгаарлагдана) — Pi 3B дээр ~0.9 GiB. Бид `swap.conf(5)`-ын **албан ёсны "Example 1"**-ийг дагаж 2 GiB-ийн уламжлалт swap файл тавина. Блокийг **бүтнээр нь** буулга:

**[🥧 Pi]**
```bash
sudo mkdir -p /etc/rpi/swap.conf.d/
sudo tee /etc/rpi/swap.conf.d/80-use-swapfile.conf > /dev/null <<EOF
[Main]
Mechanism=swapfile

[File]
FixedSizeMiB=2048
EOF
sudo reboot
```

swap-ын тохиргоо **зөвхөн дахин ачаалахад** хэрэгжинэ. 1–2 мин хүлээгээд `ssh pi`.

> Анхдагч zram+file-ийг үлдээх нь microSD-г бага элээнэ (албан ёсны зорилго нь тэр). Энэ тохиолдолд `make check`-ийн swap мөр ✗ гарах бөгөөд Лаб 1–8-ын "2.0Gi" гэсэн хүлээлтийн оронд өөрийн утгаа тайландаа бич.

**Алхам 2б — `rpi-swap` байхгүй, `dphys-swapfile` ажиллаж байгаа бол.** Энэ багцын тохиргоо Raspberry Pi-гийн баримтад ороогүй тул доорх нь уламжлалт арга:

**[🥧 Pi]**
```bash
sudo dphys-swapfile swapoff
sudo sed -i 's/^#\?CONF_SWAPSIZE=.*/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

**Алхам 3 — шалгах** (аль ч замаар явсан):

**[🥧 Pi]**
```bash
free -h
```

✅ `Swap:` мөрийн **total** баганад `2.0Gi`.

> **Санамж:** swap файл microSD дээр байгаа тул **маш удаан**. Энэ бол гүйцэтгэлийн шийдэл биш. Лаб 4-д swap ажиллаж эхэлбэл (`vmstat 1`-ийн `si/so` багана 0-ээс их) та аль хэдийн хязгаарт хүрсэн — тэр нь хэмжилт өөрөө юм.
>
> Албан ёсны эх: [raspberrypi/rpi-swap — README, swap.conf(5)](https://github.com/raspberrypi/rpi-swap)

#### cgroup

K3s-ийн баримтаар стандарт Raspberry Pi OS cgroup-ийн санах ойн хянагчийг идэвхжүүлээгүй эхэлдэг; Лаб 8-ын K3s agent, `docker stats`-ын санах ойн тоо ба ирмэгийн агентын `MemoryMax=200M` хязгаарт хэрэгтэй. Параметрийг `/boot/firmware/cmdline.txt`-ийн **цорын ганц мөрийн төгсгөлд** залгана (Debian 11 ба түүнээс өмнөх image-д зам нь `/boot/cmdline.txt`).

> ⚠️ Raspberry Pi-гийн баримт: `cmdline.txt`-ийн бүх параметр **нэг мөрөнд** байх ёстой — шинэ мөр оруулбал түүнээс хойшхыг цөм үл тоомсорлоно. Тиймээс файлыг гараар **бүү** зас, доорх командыг ашигла.

**Алхам 1 — параметр нэмэх ба дахин ачаалах.**

**[🥧 Pi]**
```bash
grep -q 'cgroup_memory=1' /boot/firmware/cmdline.txt || \
  sudo sed -i '1 s/$/ cgroup_memory=1 cgroup_enable=memory/' /boot/firmware/cmdline.txt
cat /boot/firmware/cmdline.txt
```

✅ Сүүлийн команд **НЭГ мөр** хэвлэх бөгөөд төгсгөлд нь `cgroup_memory=1 cgroup_enable=memory` байна. Тэгвэл:

**[🥧 Pi]**
```bash
sudo reboot
```

**Алхам 2 — дахин холбогдоод шалгах.**

**[🥧 Pi]**
```bash
grep -w memory /sys/fs/cgroup/cgroup.controllers
free -m | head -2
```

✅ Эхний команд `memory` үгийг агуулсан мөр хэвлэнэ. `MemTotal`-ийг Лаб 1-д бичнэ.

> Албан ёсны баримт: [K3s Requirements — Raspberry Pi (cgroups)](https://docs.k3s.io/installation/requirements) · [Kernel command line (cmdline.txt)](https://www.raspberrypi.com/documentation/computers/configuration.html#configure-the-kernel-command-line)

### Б.6 Цагийн синхрончлол (ЗААВАЛ)

Лаб 2-ын TLS гэрчилгээ, Лаб 3 ба Лаб 5-ын саатлын хэмжилт буруу цагтай үед утгагүй болдог. Pi 3B-д бодит цагийн цаг (RTC) **байхгүй** — асаах бүрд NTP-ээс цагаа авдаг.

**[🥧 Pi]**
```bash
sudo timedatectl set-timezone Asia/Ulaanbaatar
sudo timedatectl set-ntp true
timedatectl status
```

✅ `Time zone: Asia/Ulaanbaatar (+08, +0800)` ба `System clock synchronized: yes`.

❌ `synchronized: no` хэвээр бол 1–2 мин хүлээгээд дахин шалга; тэгээд ч болохгүй бол Pi интернэтэд гарч чадахгүй байна (`ping -c3 8.8.8.8`).

### Б.7 Сангаа Pi дээр байрлуулах

> ⚠️ Pi дээрх сангийн зам **заавал `~/cnc302`** (`/home/cnc302/cnc302`) байна — `edge/agent/cnc302-edge-agent.service` ба лабын заавар яг энэ замыг хүлээнэ.

**Алхам 1 — clone хийх.**

**[🥧 Pi]**
```bash
cd ~
git clone <REPO_URL> cnc302
ls ~/cnc302
```

> 💡 Багийн сан **private** бол GitHub HTTPS-ээр нэвтрэхэд нууц үгийн оронд **Personal Access Token** шаардана: `Username` → GitHub-ын нэр, `Password` → token (GitHub → Settings → Developer settings → Personal access tokens). Токенийг Pi дээр файлд бүү хадгал.

**Алхам 2 — ирмэгийн тохиргоо.**

**[🥧 Pi]**
```bash
cd ~/cnc302/edge
cp .env.example .env
nano .env
```

Дараах **хоёр мөрийг** соль (бусдыг хэвээр нь үлдээ):

| Мөр | Утга | Жишээ |
|---|---|---|
| `CLOUD_HOST=` | А.5-д олсон `<LAPTOP_IP>` | `CLOUD_HOST=192.168.1.100` |
| `DEVICE_ID=` | `pi3b-team<NN>` | `DEVICE_ID=pi3b-team07` |

Хадгалах: `Ctrl + O` → `Enter` → `Ctrl + X`.

> ⚠️ `.env`-д тайлбарыг **тусдаа мөрөнд** бич (`KEY=утга  # тайлбар` БИШ), утгыг хашилтгүй, хоосон зайгүй бич: systemd-ийн `EnvironmentFile=` мөрийн дундах `#`-ийг утгын нэг хэсэг гэж уншдаг.

**Алхам 3 — гүүрний тохиргоо үүсгэх.**

**[🥧 Pi]**
```bash
make bridge
```

✅ `✓ mosquitto/conf.d/bridge.conf үүслээ  →  192.168.1.100:1883` (таны IP) гарна.

❌ `⚠ CLOUD_HOST хэвээрээ байна` → Алхам 2-т IP-г сольж хадгалаагүй байна.

### Б.8 Ирмэгийн image ба Python орчин

**[🥧 Pi]**
```bash
cd ~/cnc302/edge
docker compose pull
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r agent/requirements.txt
```

`pip install` Pi 3B дээр **5–15 мин** үргэлжилж магадгүй — дэлгэц хэсэг хугацаанд өөрчлөгдөхгүй байсан ч **бүү тасал**.

✅ **Шалгах:**

**[🥧 Pi]**
```bash
.venv/bin/python -c "from ai_edge_litert.interpreter import Interpreter; print('LiteRT OK')"
```

`LiteRT OK` гарна.

> `ai-edge-litert` (LiteRT — TensorFlow Lite-ийн шинэ нэр) нь PyPI дээр Python 3.11 (Bookworm) ба 3.13 (Trixie)-д зориулсан `manylinux_2_27_aarch64` wheel-тэй; `numpy` ч мөн aarch64 wheel-тэй тул Pi дээр эх кодоос барихгүй. `No matching distribution` гарвал `uname -m` → `aarch64` эсэхийг шалга. Хуучин `tflite-runtime` (сүүлийн хувилбар 2.14, 2023) нь зөвхөн нөөц хувилбар.
>
> Албан ёсны баримт: [LiteRT — Migrate from tflite-runtime](https://ai.google.dev/edge/litert/migration) · [pypi: ai-edge-litert](https://pypi.org/project/ai-edge-litert/)

---

## В. 💻🥧 Хоёр машиныг холбох

Энэ бол бүх лабын суурь: Pi-гаас илгээсэн MQTT мессеж зөөврийн компьютер дээрх EMQX-д хүрэх ёстой. **Гурван терминал** зэрэг нээлттэй байна:

| Цонх | Терминал | Үүрэг |
|---|---|---|
| 1 | [🥧 Pi] | Гүүр ба агент |
| 2 | [🥧 Pi] (хоёр дахь `ssh pi`) | Гүүрний төлөв |
| 3 | [💻 Ubuntu] | Үүлэн дэх мессежийг сонсох |

### В.1 Гүүрийг асаах

Эхлээд зөөврийн компьютер дээр стек ажиллаж байгааг шалга:

**[💻 Ubuntu]**
```bash
cd ~/cnc302/stack && make up && make health
```

Дараа нь:

**[🥧 Pi]** (цонх 1)
```bash
cd ~/cnc302/edge
make up
```

✅ `docker compose ps`-ын жагсаалтад `mosquitto` → `Up`.

**[🥧 Pi]** (цонх 2 — PowerShell-ээс дахин `ssh pi`)
```bash
cd ~/cnc302/edge
make link
```

✅ `cnc302/shutis/…/bridge/state 1` гарвал **гүүр холбогдсон**. `0` бол тасарсан → В.2-ын хүснэгт. `Ctrl + C`-ээр зогсооно.

### В.2 Хоёр талаас шалгах

**[💻 Ubuntu]** (цонх 3)
```bash
mosquitto_sub -h localhost -t 'cnc302/#' -v
```

Энэ цонх **нээлттэй хүлээж** байх ёстой — хааж болохгүй.

**[🥧 Pi]** (цонх 1)
```bash
cd ~/cnc302/edge && make agent
```

✅ Цонх 3-т Pi-гийн телеметр 2 секунд тутам `cnc302/shutis/mhts/lab/pi3b-team<NN>/…` сэдвээр гарч ирнэ. Гарвал **орчин бэлэн боллоо** — цонх 1 ба 3-ыг `Ctrl + C`-ээр зогсоо.

**Гарч ирэхгүй бол Лаб 1 эхлэхгүй.** Дарааллаар нь шалга:

| Шалгах зүйл | Команд | Хүлээгдэх |
|---|---|---|
| 1. Pi үүлийг харж байна уу | 🥧 `ping -c3 <LAPTOP_IP>` | `3 received` |
| 2. Порт нээлттэй юу | 🥧 `nc -vz <LAPTOP_IP> 1883` | `succeeded` / `open` |
| 3. Гүүрний тохиргоо | 🥧 `docker compose logs mosquitto \| grep -i bridge` | `Connecting bridge` |
| 4. Сэдвийн угтвар | 🥧 `grep '^topic' mosquitto/conf.d/bridge.conf` | `cnc302/shutis/#` |
| 5. Агентын сэдэв | 🥧 `grep SITE .env` | `SITE=shutis` |

- 1-р алхам бүтэлгүйтвэл → сүлжээ (А.5): нэг subnet мөн үү, client isolation байна уу.
- 2–3-р алхамд `Connection refused`, timeout эсвэл удаа дараа тасарч байвал → А.6 галт хана ба Private профайл; зөөврийн компьютер дээр стек асаалттай эсэх.
- 4 ба 5-р алхмын `SITE` зөрүүтэй бол мессеж дамжихгүй. Энэ бол **хамгийн түгээмэл алдаа**.

### В.3 VS Code Remote-SSH холболт

1. VS Code нээ → `F1` (эсвэл `Ctrl + Shift + P`) → `Remote-SSH: Connect to Host...` гэж бичээд сонго.
2. Жагсаалтаас **`pi`**-г сонго (А.7, Алхам 3-т үүсгэсэн).
3. Платформ асуувал **Linux**.
4. Анх удаа Pi дээр VS Code Server суулгана — 3–5 мин хүлээ. Зүүн доод буланд **SSH: pi** гарна.
5. **File → Open Folder** → `/home/cnc302/cnc302` → **OK**.
6. **Terminal → New Terminal** — энэ терминал одоо **Pi дээр** ажиллана.

> VS Code-ийн баримтаар Remote-SSH-ийн алсын хостод **1 GB RAM шаардлагатай, 2 GB RAM ба 2 цөм зөвлөмжтэй** — Pi 3B яг доод хязгаар дээр. Дэмжигдэх платформ: Debian 64-бит ARMv8 (AArch64), kernel ≥ 4.18, glibc ≥ 2.28. Хэмжилт хийхийн өмнө **VS Code-ийн холболтыг таслах** — эс бөгөөс санах ойн тоо гажина (`pkill -f vscode-server`).
>
> Албан ёсны баримт: [Remote Development using SSH — System requirements](https://code.visualstudio.com/docs/remote/ssh) · [Remote Development with Linux](https://code.visualstudio.com/docs/remote/linux)

---

## Г. Бэлэн байдлын шалгалт

Лаб 1-д ирэхээс өмнө эдгээр **бүгд ✔** байх ёстой. Командын гаралтыг **хуулж** Лаб 1-ийн тайлангийн хавсралтад оруулна.

### 💻 Зөөврийн компьютер

- [ ] **[💻 PowerShell]** `wsl --version` → WSL ≥ 2.1.5; `wsl -l -v` → Ubuntu, VERSION 2
- [ ] **[💻 Ubuntu]** `docker run --rm hello-world` → `Hello from Docker!`
- [ ] **[💻 Ubuntu]** `docker info` санах ой ≈ 6 GB (А.2)
- [ ] **[💻 Ubuntu]** `cd ~/cnc302/stack && make health` → дөрвөн мөр 200
- [ ] **[💻 PowerShell]** `ipconfig` → `<LAPTOP_IP>` тодорхой, сүлжээ **Private**
- [ ] **[💻 PowerShell]** `Get-NetFirewallRule -DisplayName "CNC302 cloud"` → Enabled True
- [ ] **[💻 Ubuntu]** `python tools/sim_device.py --dry-run --devices 2 --count 3` ажиллаж байна

### 🥧 Raspberry Pi 3B

- [ ] `ssh pi` → нууц үггүй холбогдож байна
- [ ] `uname -m` → **aarch64**
- [ ] `docker run --rm hello-world` → `sudo`-гүй ажиллаж байна
- [ ] `free -h` → Swap 2.0Gi; `MemTotal`-ийг өмнө/дараа нь тэмдэглэсэн (Б.3)
- [ ] `grep -w memory /sys/fs/cgroup/cgroup.controllers` → `memory` агуулна
- [ ] `vcgencmd get_throttled` → **0x0**
- [ ] `timedatectl status` → synchronized: yes
- [ ] `cd ~/cnc302/edge && make check` → бүгд OK

### 💻🥧 Хамтдаа

- [ ] `make link` → `bridge/state 1`
- [ ] Pi-гийн агентын телеметр зөөврийн компьютерийн `mosquitto_sub`-д харагдаж байна (В.2)
- [ ] Багийн Git санд эхний commit хийгдсэн, багш унших эрхтэй

### 🖥️ Лаб 8-аас өмнө

- [ ] А.8-ын VM асаж, `ssh`-ээр холбогдож байна; `ip -4 addr` → LAN-ын хаяг (10.0.2.x БИШ)

Аль нэг нь ✘ бол **лабораторийн өмнөх өдөр** багшид хандана. **Лабораторийн 4 цагийг орчин тохируулахад зарцуулж болохгүй.**

---

## Д. Оношилгоо — түгээмэл алдаа ба шийдэл

### 💻 Зөөврийн компьютер

| Шинж тэмдэг | Шалтгаан | Шийдэл |
|---|---|---|
| `wsl --install` 0.0%-д гацах | Store-оос татаж чадахгүй | `wsl --install --web-download -d Ubuntu` |
| Docker Desktop: `WSL 2 installation is incomplete` / `WSL update failed` | WSL суугаагүй эсвэл хуучин | А.1.3-ыг дахин хий, `wsl --update`, restart |
| Docker Desktop: `Virtualization support not detected` | BIOS-д VT-x/SVM унтраалттай | А.1.1, Алхам 2 |
| `You are not allowed to use Docker, you must be in the "docker-users" group` | "All users" горимоор суулгасан | **[💻 PowerShell (Admin)]** `net localgroup docker-users $env:USERNAME /add` → Windows-оос **sign out** хийж дахин нэвтэр |
| `docker: error during connect` / `Cannot connect to the Docker daemon` | Docker Desktop ажиллаагүй | Docker Desktop нээж, **Engine running** болтол хүлээ |
| Ubuntu-д `docker: command not found` | WSL integration асаагүй | А.1.6, Алхам 3 |
| Docker Desktop гацах, компьютер удаашрах | RAM хүрэлцэхгүй | А.2-т `memory`-г 1 GB-аар багасга; Chrome-ын табуудыг хаа |
| `docker info` санах ой 50% хэвээр | `.wslconfig` буруу нэртэй/газарт | А.2-ын ⚠️; `wsl --shutdown` хийсэн эсэх |
| `Bind for 0.0.0.0:1883 failed: port is already allocated` | Windows дээр өөр MQTT брокер (Mosquitto service) ажиллаж байна | `Win + R` → `services.msc` → **Mosquitto Broker** → **Stop**, Startup type: **Disabled** |
| `pull access denied for cnc302/registry` | `--ignore-buildable`-гүй `pull` | Анхааралгүй байж болно — `make up` өөрөө барина. Эсвэл А.4, Алхам 2 |
| `pull` маш удаан, тасраад байх | Интернэт удаан | Дахин ажиллуул — татсан давхаргуудаа үргэлжлүүлнэ |
| `make health`-д `000` эсвэл `DOWN` | Контейнер асаагүй / асаж байна | 1 мин хүлээ; `make status`; `make logs S=emqx` |
| EMQX/Grafana нууц үг таарахгүй | `.env`-ийг стек анх асаасны дараа сольсон | Өгөгдлийг устгаж дахин эхлэх: `make clean` (`yes`) → `make up` |
| `/bin/sh^M: bad interpreter` | `.sh` файлд CRLF орсон | А.3, Алхам 1-ийн `core.autocrlf input` → сангаа устгаж **дахин clone** хий |
| `git clone` нэвтрэлт асуугаад бүтэлгүйтэх | Credential Manager тохируулаагүй | А.3, Алхам 1-ийн `credential.helper` мөр |

### 🥧 Raspberry Pi

| Шинж тэмдэг | Шалтгаан | Шийдэл |
|---|---|---|
| `Ping request could not find host pi-teamNN.local` | Pi асаж дуусаагүй / mDNS ажиллахгүй / Pi сүлжээнд ороогүй | 2 мин хүлээ; router-ийн жагсаалтаас IP-г ол; `<PI_IP>`-ээр холбогд |
| Pi сүлжээнд огт гарч ирэхгүй | Imager-ийн customisation хэрэгжээгүй, Wi-Fi SSID/нууц үг буруу, 5 GHz сүлжээ | Кабелиар холбо; Imager-ийг дахин нээж картаа **дахин бич**; HDMI дэлгэц + гар залгаж шалгаж болно |
| `Permission denied (publickey)` | Imager-т өөр түлхүүр буулгасан, эсвэл `ssh` буруу түлхүүр ашиглаж байна | `ssh -i "$env:USERPROFILE\.ssh\cnc302" cnc302@<PI_IP>`; хэрэглэгчийн нэр `cnc302` эсэх (`pi@` биш); болохгүй бол картаа А.7-ийн `.pub`-аар **дахин бич** |
| `WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!` | Картаа дахин бичсэн тул Pi-гийн түлхүүр солигдсон | **[💻 PowerShell]** `ssh-keygen -R pi-team<NN>.local` (ба `ssh-keygen -R <PI_IP>`) → дахин холбогд |
| `uname -m` → `armv7l` | 32-bit OS бичсэн | Б.1 — **Lite (64-bit)** |
| `Suites:` хоосон / `apt update`-д Docker-ийн 404 | Б.4, Алхам 3-ыг хэсэгчлэн хуулсан | Алхам 3-ыг блокоор нь дахин буулга |
| `permission denied ... docker.sock` | `docker` бүлэгт нэмсний дараа дахин нэвтрээгүй | `exit` → `ssh pi` |
| `exec format error` | arm64 биш (x86) image эсвэл 32-bit OS | `uname -m` → `aarch64` байх ёстой |
| `get_throttled` ≠ `0x0`, Pi санамсаргүй restart хийх | Тэжээл сул (under-voltage) | Албан ёсны 5 V / 2.5 A адаптер, богино зузаан кабель |
| `free -h` → Swap 2.0Gi биш | Reboot хийгээгүй / буруу зам | Б.5, Алхам 1-ээс дахин; `sudo reboot` |
| `make check` → `cgroup mem ✗` | `cmdline.txt` хоёр мөр болсон эсвэл reboot хийгээгүй | `cat /boot/firmware/cmdline.txt` нэг мөр эсэх; reboot |
| `pip install` маш удаан, "гацсан мэт" | Pi 3B удаан | 15 мин хүлээ; `htop`-оор CPU ачаалал байгаа эсэхийг шалга |
| `bridge/state 0`, Pi → 1883 холбогдохгүй | (а) стек асаагүй (б) Windows Firewall (в) Public профайл (г) client isolation (д) `CLOUD_HOST` буруу | (а) `make health` (б) А.6 (в) А.5 (г) лабын router/hotspot (д) `grep CLOUD_HOST ~/cnc302/edge/.env` → `make bridge` → `make restart` |

Илүү олон тохиолдол: `docs/troubleshooting.md`.

**Pi-г унтраахдаа** тэжээлийг шууд бүү сугал — microSD эвдэрнэ. `sudo poweroff` гэж бичээд **ногоон гэрэл анивчихаа больсны дараа** сугал.

---

## Эх сурвалж

| # | Эх сурвалж | Юуг баталгаажуулсан | Хандсан |
|---|---|---|---|
| 1 | [Install Docker Desktop on Windows](https://docs.docker.com/desktop/setup/install/windows-install/) | WSL 2 backend: Windows 10 22H2 (19045) / Windows 11 23H2 (22631)+, WSL ≥ 2.1.5, 8 GB RAM, virtualization; Home нь зөвхөн Linux контейнер; "Use WSL 2 instead of Hyper-V"; Subscription Service Agreement; `docker-users` бүлэг | 2026-10 |
| 2 | [Docker Desktop — WSL 2 backend](https://docs.docker.com/desktop/features/wsl/), [Best practices](https://docs.docker.com/desktop/features/wsl/best-practices/) | Use WSL 2 based engine; Resources → WSL Integration; `wsl -l -v`, `--set-version`; кодыг Linux файлын системд хадгалах | 2026-10 |
| 3 | [Microsoft — Install WSL](https://learn.microsoft.com/en-us/windows/wsl/install) | `wsl --install -d`, `--web-download`, анх асаахад UNIX хэрэглэгч үүсгэх, `wsl -l -v` | 2026-10 |
| 4 | [Git Credential Manager — WSL](https://github.com/git-ecosystem/git-credential-manager/blob/main/docs/wsl.md) | WSL-ийн Git-ийг Windows-ийн GCM-тэй холбох `credential.helper` | 2026-10 |
| 5 | [Docker Desktop — Settings](https://docs.docker.com/desktop/settings-and-maintenance/settings/) | Memory limit: Mac, Linux, Windows Hyper-V; анхдагч нь хостын 50%; WSL 2 горимд санах ойг WSL 2 VM дээр тохируулна | 2026-09 |
| 6 | [WSL — Advanced settings configuration (.wslconfig)](https://learn.microsoft.com/en-us/windows/wsl/wsl-config) | `%UserProfile%\.wslconfig`, `[wsl2] memory=`, анхдагч 50%, `wsl --shutdown` | 2026-09 |
| 7 | [New-NetFirewallRule](https://learn.microsoft.com/en-us/powershell/module/netsecurity/new-netfirewallrule) | `-LocalPort` порт/жагсаалт, `-Profile Private` | 2026-09 |
| 8 | [VirtualBox User Manual](https://www.virtualbox.org/manual/UserManual.html) | Hyper-V ажиллаж буй хост дээр гүйцэтгэл буурна, Windows Hypervisor Platform шаардлагатай; Bridged networking | 2026-09 |
| 9 | [Ubuntu release cycle](https://ubuntu.com/about/release-cycle) | Одоогийн LTS: 26.04 (24.04 LTS дэмжигдсэн) | 2026-09 |
| 10 | [K3s — Requirements](https://docs.k3s.io/installation/requirements) | server 2 цөм/2 GB, agent 1 цөм/512 MB; Raspberry Pi OS-д `cgroup_memory=1 cgroup_enable=memory`, `/boot/firmware/cmdline.txt` | 2026-09 |
| 11 | [Raspberry Pi hardware](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html), [BCM2837](https://www.raspberrypi.com/documentation/computers/processors.html#bcm2837) | Pi 3B: BCM2837, 4×Cortex-A53 @1.2 GHz, 1 GB, 100 Mb/s Ethernet, 4×USB 2.0, 2.4 GHz Wi-Fi; 80–85 °C-д throttle | 2026-09 |
| 12 | [Getting started](https://www.raspberrypi.com/documentation/computers/getting-started.html), [A new Raspberry Pi Imager](https://www.raspberrypi.com/news/a-new-raspberry-pi-imager/) | Pi 3: 5 V / 2.5 A, 12.5 W; Imager 2.0-ийн алхмууд: device → OS → storage → customisation (hostname, localisation, user, Wi-Fi, remote access/SSH public key, Raspberry Pi Connect) → write | 2026-10 |
| 13 | [vcgencmd get_throttled](https://www.raspberrypi.com/documentation/computers/os.html#vcgencmd) | бит 0 = undervoltage, бит 2 = throttled, бит 16/18 = өмнө нь болсон | 2026-09 |
| 14 | [Raspberry Pi OS](https://www.raspberrypi.com/documentation/computers/os.html) | Сүүлийн хувилбар Trixie (өмнөх Bookworm); Lite = command-line-only; 64-бит нь Pi 3-д | 2026-09 |
| 15 | [Legacy config.txt — gpu_mem](https://www.raspberrypi.com/documentation/computers/legacy_config_txt.html) | 1 GB-д анхдагч 76; legacy — Bookworm+ дээр ажиллахгүй, албан ёсоор дэмжигдэхгүй; доод утга 16 | 2026-09 |
| 16 | [Kernel command line](https://www.raspberrypi.com/documentation/computers/configuration.html) | `cmdline.txt`-ийн бүх параметр нэг мөрөнд | 2026-09 |
| 17 | [raspberrypi/rpi-swap](https://github.com/raspberrypi/rpi-swap) | `dphys-swapfile`-ийг орлоно; `/etc/rpi/swap.conf.d/`; `Mechanism=auto` = zram+file; Example 1 (`swapfile`, `FixedSizeMiB=2048`); өөрчлөлтийн дараа reboot | 2026-09 |
| 18 | [Install Docker Engine on Debian](https://docs.docker.com/engine/install/debian/) | Trixie 13 / Bookworm 12, arm64; apt repository-ийн алхам; convenience script зөвхөн туршилт/хөгжүүлэлтэд | 2026-09 |
| 19 | [Install Docker Engine on Raspberry Pi OS (32-bit)](https://docs.docker.com/engine/install/raspberry-pi-os/) | Engine v28 нь armhf-ийн сүүлийнх; 64-бит ARM-д Debian arm64 багц | 2026-09 |
| 20 | [Linux post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/) | `usermod -aG docker`, дахин нэвтрэх, docker бүлгийн эрсдэл | 2026-09 |
| 21 | [JSON File logging driver](https://docs.docker.com/engine/logging/drivers/json-file/) | `daemon.json`-ийн `log-opts` мөр утгатай; зөвхөн шинэ контейнерт | 2026-09 |
| 22 | [VS Code — Remote Development using SSH](https://code.visualstudio.com/docs/remote/ssh), [with Linux](https://code.visualstudio.com/docs/remote/linux) | 1 GB RAM шаардлагатай, 2 GB + 2 цөм зөвлөмжтэй; Debian 64-бит ARMv8, kernel ≥ 4.18, glibc ≥ 2.28 | 2026-09 |
| 23 | [pypi: ai-edge-litert](https://pypi.org/project/ai-edge-litert/), [pypi: numpy](https://pypi.org/project/numpy/) | ai-edge-litert: cp311/cp313 `manylinux_2_27_aarch64`; numpy aarch64 wheel | 2026-09 |
