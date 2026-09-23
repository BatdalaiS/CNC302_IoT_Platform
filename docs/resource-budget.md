# Нөөцийн төсөв — хоёр давхаргат байрлуулалт

Энэ бол **чиглүүлэх тооцоо**. Бодит утгыг Лаб 1-д өөрсдөө хэмжинэ.

---

## 1. 🥧 Raspberry Pi 3B — 1 GB-ын арифметик

### Юу хаана явдаг вэ

| Хэсэг | MiB | Тэмдэглэл |
|---|---|---|
| Нийт физик санах ой | 1024 | албан ёсны үзүүлэлт: 1 GB |
| GPU-д (`gpu_mem`) | −16…−76 | 1 GB-тай загварт анхдагч **76**. `gpu_mem` нь legacy тохиргоо — Bookworm ба түүнээс хойш албан ёсоор дэмжигдэхгүй, тиймээс SETUP.md Б.3-т өмнө/дараа нь **хэмжинэ** |
| Цөм + firmware | ~85 | таамаг |
| **Системд харагдах (`MemTotal`)** | **~925** (хэмжинэ) | `free -m` энийг харуулна |
| Pi OS Lite, headless, амарч байгаа | −90…−130 | systemd, sshd, journald |
| Docker демон | −60…−80 | `dockerd` + `containerd` |
| **Ажилд боломжтой** | **~720…780** | |

### Ирмэгийн үйлчилгээний төсөв

| Үйлчилгээ | Compose хязгаар | Бодит амралтын хэрэглээ | Тэмдэглэл |
|---|---|---|---|
| `mosquitto` | 128 MiB | 12–25 MiB | Дараалал дүүрэхэд өснө: 100k мессеж × 250 B ≈ 25 MiB |
| ирмэгийн агент (venv) | 200 MiB (systemd) | 45–70 MiB | numpy ~25 MiB эзэлнэ |
| + TFLite дүгнэлт (Лаб 6) | ↑ | +40…+90 MiB | загварын хэмжээ ба цонхноос хамаарна |
| VS Code Remote сервер | — | **150–250 MiB** | ⚠ хэмжилтийн өмнө таслах! |

**Нийлбэр (Лаб 1–5):** ~120 MiB → **600 MiB илүүдэлтэй.** Тав тухтай.
**Нийлбэр (Лаб 6, дүгнэлттэй):** ~200 MiB → **520 MiB илүүдэлтэй.** Хангалттай.
**Лаб 8 (K3s):** доорх §3-ыг үзнэ үү — энэ нь хамгийн чанга.

### Хэзээ анхаарах вэ

```bash
free -m | awk '/Mem:/{print $7 " MiB available"}'
```

| Үлдэгдэл | Утга |
|---|---|
| > 400 MiB | хэвийн |
| 150–400 MiB | болгоомжтой — шинэ үйлчилгээ нэмэхээс өмнө хэмж |
| < 150 MiB | **аюултай** — swap идэвхжиж, бүх саатал 10–100 дахин өснө |
| swap `si/so` > 0 | аль хэдийн хязгаарт хүрсэн. Энэ нь **хэмжилт**, алдаа биш. |

`tools/measure_stack.sh --role edge` эдгээрийг автоматаар шалгана.

---

## 2. 💻 Зөөврийн компьютер — үүлний давхарга

| Үйлчилгээ | Профайл | Compose хязгаар | Хүлээгдэх хэрэглээ | Тэмдэглэл |
|---|---|---|---|---|
| `emqx` | core | 1024 MiB | 150–250 MiB | Холболт нэмэгдэхэд ~4 KiB/холболт |
| `influxdb` | core | 1024 MiB | 250–500 MiB | Бичилтийн ачаалалтай өснө |
| `grafana` | core | 512 MiB | 120–200 MiB | Самбарын тоогоор өснө |
| `registry` | core | 384 MiB | 60–110 MiB | FastAPI + SQLite |
| `nodered` | pipeline | 512 MiB | 120–200 MiB | Урсгалын нарийвчлалаас |
| `dex` | app | 256 MiB | 30–60 MiB | |
| `graphql-api` | app | 512 MiB | 80–150 MiB | Python/FastAPI |
| `ollama` | ai | 4096 MiB | загвараас | qwen2.5:1.5b q4 ≈ 1.2–1.6 GiB + KV |
| `thingsboard` | tb (сонголт) | 2500 MiB | 1200–1800 MiB | зөвхөн Лаб 2-ын харьцуулалт; албан ёсны заавар хөгжүүлэлтэд ч 4 GB RAM |

### Профайлын нийлбэр

| Хослол | Хязгаарын нийлбэр | Практикт | Docker Desktop-д хэрэгтэй |
|---|---|---|---|
| core | 2.9 GiB | 0.6–1.1 GiB | 4 GB |
| core + pipeline | 3.4 GiB | 0.7–1.3 GiB | 4 GB |
| core + pipeline + app | 4.2 GiB | 0.8–1.5 GiB | 4 GB |
| + ai (Лаб 8) | 8.2 GiB | 2.0–3.1 GiB | **6 GB** |
| core + tb (Лаб 2 сонголт) | 5.4 GiB | 1.8–2.9 GiB | **6 GB** |

"Практикт" ба "Хүлээгдэх хэрэглээ" багана нь **таамаг** — `docker stats`-аар өөрсдөө хэмжинэ. Лаб 8-д үүн дээр K3s server VM (4 GB) нэмэгдэнэ → зөөврийн компьютерт **16 GB RAM тав тухтай** (§3).

> **Харьцуулалт:** ThingsBoard ГАНЦААРАА 1.2–1.8 GiB эзэлнэ — энэ нь Pi 3B-ийн НИЙТ санах ойноос **хоёр дахин их**. Лаб 2-ын хяналтын асуултад: "яагаад ирмэг дээр бүрэн платформ ажиллуулж болохгүй вэ?" гэдгийн тоон хариулт нь энэ.

---

## 3. Лаб 8 — K3s: server нь VM дээр, Pi нь agent

K3s-ийн албан ёсны доод шаардлага: **server 2 цөм / 2 GB**, **agent 1 цөм / 512 MB**. Тиймээс K3s **server** нь зөөврийн компьютер дээрх Ubuntu Server VM-д, Raspberry Pi 3B нь зөвхөн **agent** болж нэгдэнэ (дэлгэрэнгүй: `lab08/k3s/README.md`). Pi дээр Compose-ийн mosquitto ба Docker демоныг зогсооно — хоёуланг зэрэг ажиллуулах орон зай байхгүй, мөн ижил client ID-тай хоёр гүүр `bridge/state`-ийг анивчуулна.

### 3.1 🥧 Pi 3B (agent)

| Хэсэг | MiB | Эх сурвалж / тэмдэглэл |
|---|---|---|
| `MemTotal` | ~925 | SETUP.md Б.3-т хэмжсэн утгаа бич |
| OS (Lite, headless) | 90–130 | таамаг — хэмжинэ |
| k3s agent (containerd + kubelet + flannel) | **≈ 268** | K3s Resource Profiling-ийн **Pi 4B** хэмжилт (Pi 3B-д албан ёсны тоо алга) |
| **Pod-уудад бодитоор үлдэх** | **≈ 525–565** | 925 − OS − agent |

Товлогч (scheduler) бодит RSS-ийг биш, **Allocatable** ба `requests`-ийн нийлбэрийг харьцуулна. K3s-ийн kubelet-д **reserved санах ой тавиагүй**, hard eviction нь зөвхөн дискний (`imagefs`/`nodefs` 5 %) — санах ойн босго **байхгүй** (K3s CIS Self-Assessment). Тиймээс **Allocatable ≈ Capacity ≈ 925 Mi**.

| Pod | `requests` |
|---|---|
| `mosquitto` | 32 Mi |
| `edge-agent` × N | 96 Mi × N (N = 1 → нийт **128 Mi**) |

**HPA-ийн гол зөрчил (Лаб 8):** товлогчийн тооцоогоор `32 + 96·N ≤ 925` → **N_sched ≈ 9** хүртэл "багтана". Гэтэл бодит ≈ 545 MiB-д ~110 MiB-ийн агент **N_real ≈ 4–5**-аас илүү багтахгүй. Үр дүн нь `Pending` биш — цөмийн OOM killer (`OOMKilled`) эсвэл swap дээр мөлхөх. Аль нь болсныг `kubectl top` + `free -m` + `vmstat`-аар хэмжиж нотолно.

### 3.2 🖥️ Server VM ба 💻 зөөврийн компьютер

| Хэсэг | Утга | Эх сурвалж |
|---|---|---|
| K3s server + 1 agent (ачаалалгүй) | ≈ **1428 M** | K3s Resource Profiling (x86_64) |
| VM-ийн RAM | доод **2 GB**, санал **4 GB**; ≥ 2 vCPU | K3s Requirements |
| Docker Desktop (үүлний стек + Ollama) | 6 GB | §2, SETUP.md А.2 |
| **Зөөврийн компьютерт нийт** | 6 + 4 GB + хост OS → **16 GB** тав тухтай | |

> `traefik`/`servicelb`-ийг унтраах эсэх нь **server VM**-ийн суулгалтын асуудал (Pi биш) — `lab08/k3s/README.md`.

---

## 4. Санамж

- `deploy.resources.limits` нь **хязгаар** л тавьдаг, нөөц **баталгаажуулдаггүй**. Pi дээр хязгаарыг давсан контейнерийг цөм OOM-оор устгана; лог нь `docker inspect <c> | grep OOMKilled`.
- Cgroup-ийн санах ойн хянагч (`cgroup_memory=1 cgroup_enable=memory`) нь `docker stats`-ын санах ойн тоо ба K3s agent-д хэрэгтэй (SETUP.md Б.5).
- Идэвхтэй хөргөлт байхгүй бол Pi 3B ачаалал дор 80–85 °C-д хүрч давтамжаа бууруулна — бүх хэмжилт гажина. `vcgencmd get_throttled` нь **`0x0`** байх ёстой.
- microSD-гийн бичих хурд нь mosquitto persistence ба swap-ыг зэрэг хязгаарлана. Лаб 5-д үүнийг бодитоор хэмжинэ.
- Хэмжилтийн өмнө **VS Code Remote серверийг таслах**: `pkill -f vscode-server`. VS Code-ийн баримтаар Remote-SSH-ийн хостод 1 GB RAM *шаардлагатай* — Pi 3B-д энэ бол том зардал; ялгааг Лаб 1-д хэмж.

---

## Эх сурвалж

| # | Эх сурвалж | Юуг баталгаажуулсан | Хандсан |
|---|---|---|---|
| 1 | [Legacy config.txt — gpu_mem](https://www.raspberrypi.com/documentation/computers/legacy_config_txt.html) ([эх 1](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/legacy_config_txt/legacy.adoc), [эх 2](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/legacy_config_txt/memory.adoc)) | 1 GB-д анхдагч 76; legacy, Bookworm+ дээр дэмжигдэхгүй | 2026-09 |
| 2 | [K3s — Requirements](https://docs.k3s.io/installation/requirements) | server 2 цөм/2 GB, agent 1 цөм/512 MB; Raspberry Pi-гийн cgroup | 2026-09 |
| 3 | [K3s — Resource Profiling](https://docs.k3s.io/reference/resource-profiling) | agent (Pi 4B) ≈ 268 M; server + 1 agent (x86_64) ≈ 1428 M | 2026-09 |
| 4 | [K3s — CIS 1.12 Self-Assessment](https://docs.k3s.io/security/self-assessment-1.12) | kubelet: reserved алга, `evictionHard` зөвхөн imagefs/nodefs | 2026-09 |
| 5 | [Kubernetes — Reserve Compute Resources](https://kubernetes.io/docs/tasks/administer-cluster/reserve-compute-resources/), [Resource Management for Pods](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/) | Allocatable = Capacity − reserved − eviction; товлогч `requests`-ээр шийднэ | 2026-09 |
| 6 | [ThingsBoard CE — Docker](https://thingsboard.io/docs/installation/docker/) | PoC-д 4 GB RAM | 2026-09 |
| 7 | [Compose Deploy Specification — resources](https://docs.docker.com/reference/compose-file/deploy/) | `limits` нь платформ хуваарилахыг хориглох дээд хязгаар, `reservations` нь баталгаа | 2026-09 |
| 8 | [VS Code — Remote Development using SSH](https://code.visualstudio.com/docs/remote/ssh) | алсын хостод 1 GB RAM шаардлагатай | 2026-09 |
| 9 | [Frequency management and thermal control](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#frequency-management-and-thermal-control) ([эх](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/raspberry-pi/frequency-management.adoc)) | 80–85 °C throttle | 2026-09 |
