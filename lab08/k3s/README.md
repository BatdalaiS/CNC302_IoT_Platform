# K3s манифестууд — Лаб 8 (VM дээрх server + Raspberry Pi 3B agent)

XIV долоо хоногийн бие даалтаар энэ файлыг **бүтнээр уншиж**, `*.yaml`-уудыг ойлгосон байх ёстой. §3.1–3.2 (VM бэлтгэх, K3s server суулгах)-ыг **лабораторийн өмнө** хийж ирнэ.

## 1. Топологи — юуг хаана ажиллуулах вэ

K3s-ийн албан ёсны **доод** шаардлага:

| Зангилаа | CPU | RAM | Эх сурвалж |
|---|---|---|---|
| Server | 2 цөм | 2 GB | [K3s Requirements](https://docs.k3s.io/installation/requirements) |
| Agent | 1 цөм | 512 MB | мөн тэнд |

Raspberry Pi 3B-д **1 GB** RAM, `free -m`-ийн `MemTotal` ~925 MiB. Энэ нь server-ийн доод шаардлагын **талаас бага** — тиймээс Pi 3B дээр K3s **server ажиллуулахгүй**. K3s-ийн өөрийн хэмжилт ч үүнийг баталдаг: ачаалалтай нэг зангилааны server Pi 4B дээр **1588 M** санах ой эзэлсэн ([Resource Profiling](https://docs.k3s.io/reference/resource-profiling)). Харин **agent** Pi 4B дээр **268 M** эзэлсэн — 1 GB-д багтана.

| Үүрэг | Төмөр | Архитектур | Юу ажиллах вэ |
|---|---|---|---|
| **K3s server** (control plane + SQLite) | зөөврийн компьютер дээрх **Ubuntu Server LTS VM** (VirtualBox, Bridged Adapter) | amd64 | API server, scheduler, coredns, metrics-server, local-path-provisioner |
| **K3s agent** | **Raspberry Pi 3B** | arm64 | `mosquitto` (гүүр) + `edge-agent` — **nodeSelector-оор хадсан** |
| Үүл (өөрчлөгдөхгүй) | зөөврийн компьютер, Docker Compose | amd64 | EMQX, InfluxDB, Grafana, registry, Node-RED, Dex, GraphQL, Ollama |

> **EMQX/InfluxDB/Grafana-г кластер руу бүү оруул.** Тэд үүлний давхаргад Compose дээр хэвээр үлдэнэ. Энэ лабораторийн K3s-ийн зорилго бол **ирмэгийн** ачааллыг зохион байгуулах, үүлийг дахин барих биш.

**Порт** — K3s-ийн inbound дүрмийн хүснэгтээс энэ топологид хэрэгтэй гурав ([Requirements → Networking](https://docs.k3s.io/installation/requirements#networking)):

| Протокол | Порт | Эх → Хүрэх | Юунд |
|---|---|---|---|
| TCP | **6443** | agent (Pi) → server (VM) | K3s supervisor ба Kubernetes API |
| UDP | **8472** | бүх зангилаа ↔ бүх зангилаа | Flannel VXLAN (pod сүлжээ) |
| TCP | **10250** | бүх зангилаа ↔ бүх зангилаа | kubelet metrics ба API — **metrics-server, тиймээс HPA-д заавал** |

> K3s-ийн баримт: *"The VXLAN port on nodes should not be exposed to the world as it opens up your cluster network to be accessed by anyone."* 8472/udp-г зөвхөн лабораторийн LAN дотор нээ.

---

## 2. Санах ойн тооцоо (ЭНЭ ХЭСГИЙГ АЛГАСАЖ БОЛОХГҮЙ)

Хоёр зангилааны төсвийг **тусад нь** тооцно. Pi-гийн тоонуудын эх сурвалж: K3s agent — [Resource Profiling](https://docs.k3s.io/reference/resource-profiling) (Pi 4B, K3s v1.26.5, 95-р процентиль; Pi 3B дээр **өөрсдөө хэмж**); OS, Docker, агент — курсын хэмжилт (`docs/resource-budget.md`).

### 2.1 🥧 Pi 3B (agent) — бодит санах ой

```
MemTotal (free -m, Лаб 1-д ХЭМЖСЭН утга)         ≈ 925 MiB
  − Raspberry Pi OS Lite (systemd, sshd, …)      −90…−130 MiB
  − k3s agent (kubelet + containerd + flannel)   ≈ −270 MiB   (docs: 268 M)
  ─────────────────────────────────────────────────────────────
  Pod-уудад БОДИТООР үлдэх                        ≈ 525…565 MiB
  (Docker демон ажиллаж байвал                    −60…−80 MiB)
```

| Хэрэглэгч | Бодит RSS | `requests` / `limits` | Тэмдэглэл |
|---|---:|---|---|
| k3s agent (pod биш) | ~270 MiB | — | systemd үйлчилгээ — товлогч **харахгүй** |
| `mosquitto` | 12–25 MiB | 32Mi / 96Mi | дараалал дүүрэхэд өснө |
| `edge-agent` × 1 | 55–110 MiB | 96Mi / 160Mi | TFLite дүгнэлттэй бол дээд утга |
| **Нийт (N = 1)** | **≈ 450–540 MiB** | | ~400 MiB илүүдэл |

### 2.2 🥧 Pi 3B — товлогчийн (scheduler) харах тоо

Товлогч бодит RSS-ийг биш, зангилааны **Allocatable** ба pod-уудын **`requests`**-ийн нийлбэрийг харьцуулна ([Resource Management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)). `Allocatable = Capacity − kube-reserved − system-reserved − eviction-hard` ([Reserve Compute Resources](https://kubernetes.io/docs/tasks/administer-cluster/reserve-compute-resources/)). K3s-ийн kubelet-д **reserved тавиагүй**, hard eviction нь зөвхөн дискний (`imagefs.available<5%,nodefs.available<5%`) — санах ойн босго **байхгүй** ([CIS 1.12 Self-Assessment](https://docs.k3s.io/security/self-assessment-1.12)-ийн kubelet тохиргоо). Тиймээс:

Өөрийн Pi дээр шалга (CIS хуудасны audit командтай ижил):

```bash
# 🥧 Pi — kubelet ямар тугтай ажиллаж байна
sudo journalctl -u k3s-agent | grep 'Running kubelet' | tail -n1 | tr ' ' '\n' | grep -E 'eviction-hard|fail-swap-on|reserved'
```

```
Allocatable (Pi) ≈ Capacity ≈ 925 Mi       ← kubectl describe node <pi>-ээр БАТАЛ
requests: mosquitto 32 + edge-agent 96 × N
  N = 1 → 128 Mi    N = 3 → 320 Mi    N = 8 → 800 Mi    N = 9 → 896 Mi
```

**Гол зөрчил:** товлогчийн хувьд N ≈ 9 хүртэл "багтана", гэтэл бодит сул санах ой (~545 MiB) ~110 MiB-ийн агентыг **4–5**-аас илүү даахгүй. Товлогч k3s agent ба OS-ийн ~380 MiB-ийг **мэдэхгүй** — reserved тавиагүй учраас. Үр дүн нь `Pending` **биш**, харин цөмийн OOM killer (`OOMKilled`, Exit 137) эсвэл swap дээр мөлхөх. Pi-д 2 GB swap бий (SETUP Б.5): Kubernetes-ийн анхдагч `NoSwap` горимд **pod-ууд swap ашиглахгүй**, харин k3s agent зэрэг systemd үйлчилгээ ашиглаж чадна ([Swap memory management](https://kubernetes.io/docs/concepts/cluster-administration/swap-memory-management/)) — зангилаа удаашрах боловч амьд үлдэж магадгүй. `requests` бол **амлалт**, `limits` бол **хана**, **RSS бол үнэн** — гурвыг нь `kubectl top` + `free -m`-ээр зэрэг хэмжиж тайландаа бич.

> **coredns / metrics-server / local-path-provisioner** хаана байна? Тэд nodeSelector-гүй тул товлогч аль ч зангилаанд тавьж болно. `kubectl get pods -A -o wide`-аар шалга. Pi дээр буусан бол тэдний санах ойг Pi-гийн төсөвт нэм.

### 2.3 🖥️ Server VM ба 💻 зөөврийн компьютер

| Хэсэг | Санах ой | Эх сурвалж |
|---|---|---|
| K3s server + 1 agent, workload-гүй (Kine/SQLite, x86_64) | **1428 M** | [Resource Profiling](https://docs.k3s.io/reference/resource-profiling) |
| VM-д өгөх RAM | доод **2 GB**, санал **4 GB** | Requirements; 2 GB дээр Ubuntu + K3s server бараг зайгүй |
| VM-д өгөх vCPU | доод **2** | Requirements |
| Docker Desktop (үүлний стек + Ollama) | **6 GB** | SETUP А.2 |
| **Зөөврийн компьютерт нийт** | 6 + 4 GB + хост OS → **16 GB** тав тухтай | |

> **8 GB-тай зөөврийн компьютер:** VM-д 2 GB өг, Алхам 7–8-ын өмнө `docker compose stop ollama` хий (K3s-ийн алхамд LLM хэрэггүй). EMQX-ийг **зогсоож болохгүй** — гүүр түүн рүү холбогдоно.

---

## 3. Суулгах

### 3.1 🖥️ VM бэлтгэх (VirtualBox, нэг удаа)

1. **Ubuntu Server 24.04 LTS** (эсвэл 26.04 LTS) amd64 ISO — [ubuntu.com](https://ubuntu.com/about/release-cycle).
2. VirtualBox → New VM: **≥ 2 vCPU**, **4 GB** RAM (доод 2 GB), 20 GB диск.
3. **Settings → Network → Adapter 1 → Attached to: Bridged Adapter**, Name: LAN-д холбогдсон физик адаптер (кабель байвал Ethernet). **Нэг л адаптер** — NAT адаптер нэмэхгүй.
   - Яагаад Bridged: VirtualBox-ийн хүснэгтээр Bridged горимд VM **LAN-аас шууд хүрэгдэнэ** (VM←Net/LAN = +), харин NAT горимд зөвхөн port forwarding-оор ([VirtualBox: Networking Modes](https://www.virtualbox.org/manual/topics/networkingdetails.html)). 8472/udp VXLAN ба 10250/tcp-г NAT-аар дамжуулах нь хэрэггүй төвөг.
   - Wi-Fi-д bridge хийхэд VirtualBox MAC хаягийг орлуулдаг бөгөөд Linux хост дээр зөвхөн IPv4/IPv6-ийг дэмжинэ (мөн тэнд). Кабель илүү найдвартай (SETUP А.5-ын зөвлөмж).
4. Ubuntu-г суулгахдаа **OpenSSH server**-ийг сонго. Суусны дараа:

```bash
# 🖥️ VM
ip -4 addr show scope global      # ← VM-ийн LAN IP (жишээ 192.168.1.60). Зөөврийн компьютерийнхээс ӨӨР байх ёстой
hostnamectl                       # hostname Pi-гийнхээс ӨӨР байх ёстой (K3s Quick-Start)
```

> VM-ийн IP DHCP-ээр өөрчлөгдвөл agent server-ээ алдана. Роутер дээр DHCP reservation хий, эсвэл лабораторийн эхэнд IP-г дахин шалга.

> **Windows дээр Docker Desktop (WSL2 / Hyper-V) + VirtualBox:** VirtualBox нь Hyper-V ажиллаж буй хост дээр Hyper-V-г виртуалчлалын хөдөлгүүр болгон ашиглана, гэхдээ *"host systems might experience significant Oracle VirtualBox performance degradation"*; Windows Hypervisor Platform идэвхтэй байх ёстой ([VirtualBox: Using Hyper-V with Oracle VirtualBox](https://www.virtualbox.org/manual/UserManual.html)). VM-ийн цонхны CPU дүрс (яст мэлхий) үүнийг харуулна.

### 3.2 🖥️ K3s server суулгах

> Албан ёсны баримт: [K3s Quick-Start](https://docs.k3s.io/quick-start) · [Managing Packaged Components](https://docs.k3s.io/installation/packaged-components)

```bash
# 🖥️ VM
curl -sfL https://get.k3s.io | sh -s - \
  --write-kubeconfig-mode 644 \
  --disable traefik \
  --disable servicelb
sudo cat /var/lib/rancher/k3s/server/node-token    # ← K3S_TOKEN (нууц — Git-д бүү оруул)
kubectl get nodes -o wide                          # INTERNAL-IP = VM-ийн LAN IP байх ёстой
```

Анхдагчаар K3s `coredns`, `traefik`, `local-storage`, `metrics-server`-ийг AddOn хэлбэрээр суулгаж, `servicelb`-г асаадаг. Юуг үлдээж, юуг унтраах вэ:

| Бүрэлдэхүүн | Шийдвэр | Үндэслэл (баримтаас) |
|---|---|---|
| `traefik` | **унтраана** | HTTP(S) Ingress controller; LoadBalancer Service-ээр 80/443-ийг эзэлнэ ([Networking Services](https://docs.k3s.io/networking/networking-services)). Бидний урсгал MQTT (TCP) бөгөөд NodePort-оор гарна — HTTP Ingress хэрэггүй. |
| `servicelb` | **унтраана** | `type: LoadBalancer` Service бүрт DaemonSet үүсгэж, **зангилаа бүр дээр** `svc-` pod тавьдаг (мөн тэнд). Traefik-тэй бол тэр pod **Pi дээр ч** буух байсан. Бидэнд LoadBalancer Service байхгүй. |
| `metrics-server` | **ҮЛДЭЭНЭ** | HPA ба `kubectl top`-ийн эх сурвалж ([HPA walkthrough](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale-walkthrough/)). Унтраавал Алхам 8 бүхэлдээ ажиллахгүй. |
| `coredns` | **ҮЛДЭЭНЭ** | `edge-agent` нь `mosquitto` гэсэн Service нэрийг DNS-ээр шийднэ. |
| `local-storage` | **ҮЛДЭЭНЭ** | `mosquitto-data` PVC-ийн `local-path` StorageClass. |

`--write-kubeconfig-mode 644` — kubeconfig (`/etc/rancher/k3s/k3s.yaml`) анхдагчаар root-ийн 600 горимтой; 644 нь `sudo`-гүй `kubectl` ажиллуулах боломж өгнө ([k3s server CLI](https://docs.k3s.io/cli/server)). Бүх `kubectl` командыг **VM дээр** ажиллуулна.

### 3.3 Галт хана — гурван давхарга

| Хаана | Юу хийх | Үндэслэл |
|---|---|---|
| 🖥️ VM (Ubuntu) | анхдагчаар юу ч хийхгүй — *"ufw by default is initially disabled"* ([Ubuntu Server: Firewalls](https://ubuntu.com/server/docs/how-to/security/firewalls/)). Асаасан бол K3s зөвлөмж: `ufw disable`, эсвэл `ufw allow 6443/tcp`, `ufw allow from 10.42.0.0/16 to any`, `ufw allow from 10.43.0.0/16 to any` + Pi-гээс ирэх `8472/udp`, `10250/tcp` | [K3s Requirements](https://docs.k3s.io/installation/requirements) |
| 💻 Windows хост | VM-ийн портуудад **дүрэм хэрэггүй**: Bridged горимд VirtualBox пакетуудыг *"directly, circumventing your host operating system's network stack"* солилцоно ([VirtualBox Networking](https://www.virtualbox.org/manual/topics/networkingdetails.html)). Харин Pi-гийн гүүр **хост дээрх EMQX**-д 1883-аар холбогдох тул SETUP А.6-гийн дүрэм хэвээр хэрэгтэй. | |
| 🥧 Pi | Raspberry Pi OS дээр галт хана асаасан бол VM-ээс ирэх `8472/udp` ба `10250/tcp`-г нээ. | Inbound Rules хүснэгт |

### 3.4 🥧 Pi 3B-г agent болгож нэгтгэх

**(а) cgroup.** K3s-ийн баримт: *"Standard Raspberry Pi OS installations do not start with cgroups enabled. K3S needs cgroups to start the systemd service. cgroups can be enabled by appending `cgroup_memory=1 cgroup_enable=memory` to `/boot/firmware/cmdline.txt`."* Debian 11 ба түүнээс өмнөх Pi OS-д зам нь `/boot/cmdline.txt` ([Requirements → Raspberry Pi](https://docs.k3s.io/installation/requirements#operating-systems)). SETUP Б.5-д үүнийг аль хэдийн хийсэн — зөвхөн шалга:

```bash
# 🥧 Pi
grep -o 'cgroup[^ ]*' /boot/firmware/cmdline.txt   # cgroup_enable=memory ба cgroup_memory=1
uname -m                                           # aarch64 (arm64) байх ЁСТОЙ
```

> **VXLAN модулийн тэмдэглэл** зөвхөн Pi дээрх **Ubuntu** 21.10–23.10-д хамаарна (`sudo apt install linux-modules-extra-raspi`; 24.04 ба түүнээс хойш шаардлагагүй). Raspberry Pi OS-д энэ алхам **байхгүй**. Мөн баримтад: Raspberry Pi OS нь Debian-д суурилсан тул iptables-ийн мэдэгдэж буй алдаанд өртөж болзошгүй — [Known Issues](https://docs.k3s.io/known-issues) (`--prefer-bundled-bin`).

**(б) microSD ба etcd-ийн анхааруулга.** Баримтад: *"etcd is write intensive; SD cards and eMMC cannot handle the IO load"* — Pi-д гадаад SSD зөвлөнө. Энэ нь **datastore**-т хамаатай. Бидний datastore (анхдагч SQLite — [Cluster Datastore](https://docs.k3s.io/datastore)) **VM дээр**, `/var/lib/rancher/k3s/server` дор байна. Pi-гийн agent datastore агуулдаггүй; microSD-д зөвхөн containerd-ийн дүрс, pod-ын лог ба `mosquitto` PVC бичигдэнэ. Тиймээс agent-ийг microSD дээр ажиллуулж болно — гэхдээ дүрс татах/задлах нь *"highly CPU and IO bound"* ([Resource Profiling](https://docs.k3s.io/reference/resource-profiling)) тул эхний байршуулалт удаан.

**(в) Compose-ийн ирмэгийн стек ба native агентыг ЗОГСООНО — заавал.**

```bash
# 🥧 Pi
cd ~/cnc302/edge && docker compose down           # Compose-ийн mosquitto
sudo systemctl stop cnc302-edge-agent 2>/dev/null # Лаб 5-ын systemd агент (байвал)
pkill -f edge_agent.py                            # гараар ажиллуулсан агент (байвал)
sudo systemctl stop docker.socket docker          # Docker демон — доорх тооцоог үз
free -m                                           # available ≥ 700 MiB байх ёстой
```

Яагаад:

1. **Функциональ шалтгаан (заавал).** Compose-ийн mosquitto ба K3s-ийн mosquitto хоёулаа EMQX рүү **ижил** `remote_clientid edge-pi3b-01`-ээр гүүр тавина. MQTT 5.0: *"If the ClientID represents a Client already connected to the Server, the Server sends a DISCONNECT packet to the existing Client with Reason Code of 0x8E (Session taken over)"* ([MQTT 5.0 §3.1.4](https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html)) — хоёр гүүр бие биенээ ээлжлэн тасална. Хоёр агент нэг `DEVICE_ID`-аар давхар нийтэлнэ.
2. **Санах ойн шалтгаан (зөвлөмж).** K3s өөрийн **embedded containerd**-тэй (*"K3s includes and defaults to containerd"* — [Advanced Options](https://docs.k3s.io/advanced)); Docker өөрийн `dockerd` + `containerd`-г тусад нь ажиллуулна. Тэд дүрсийн сангаа хуваалцдаггүй, бие биедээ саад болохгүй, гэхдээ Docker сул байхдаа ч 60–80 MiB эзэлнэ — энэ нь §2.1-ийн ~545 MiB-ийн **12–15 %**, ойролцоогоор **нэг `edge-agent`**-ийн хэмжээ. HPA-гийн туршилтад энэ зөрүү шууд харагдана. Лаб 8-д Pi дээр Docker **огт хэрэггүй** (дүрсийг зөөврийн компьютер дээр барина, §4).

**(г) Нэгтгэх.** Токен ба URL-ийн хэлбэр яг Quick-Start-ынх:

```bash
# 🥧 Pi — <VM-IP> ба <token>-ийг §3.2-оос
curl -sfL https://get.k3s.io | K3S_URL=https://<VM-IP>:6443 K3S_TOKEN=<token> sh -
systemctl status k3s-agent --no-pager | head -5
```

**(д) Шошго тавих** — 🖥️ VM дээр:

```bash
kubectl get nodes -o wide                                   # Pi Ready болтол 1–3 мин
kubectl label nodes <pi-зангилааны-нэр> cnc302/layer=edge   # kubernetes.io-ийн "Assign Pods to Nodes" хэлбэр
kubectl get nodes -L kubernetes.io/arch,cnc302/layer        # VM=amd64, Pi=arm64 + edge
kubectl top nodes                                           # ХОЁР мөр гарвал metrics-server → 10250 ажиллаж байна
```

Шошгыг нэгтгэх үед ч тавьж болно: `… sh -s - --node-label cnc302/layer=edge`. Анхаар: *"The two options only add labels and/or taints at registration time"* — дараа нь `kubectl label`-аар өөрчилнө ([k3s agent CLI](https://docs.k3s.io/cli/agent)).

**Яагаад хадах (pin) заавал вэ.** Кластер **гетероген**: VM нь amd64, Pi нь arm64. `kubernetes.io/arch` шошгыг kubelet өөрөө `runtime.GOARCH`-аар бөглөдөг — *"This can be handy if you are mixing ARM and x86 nodes"* ([Well-Known Labels](https://kubernetes.io/docs/reference/labels-annotations-taints/)). Хадахгүй бол товлогч `edge-agent`-ийг илүү сул VM дээр тавьж магадгүй: (1) arm64 дүрс VM дээр байхгүй (зөвхөн Pi-д импортолсон), (2) агент VM-ийн `/sys/class/thermal`-ийг уншиж **худал** өгөгдөл нийтэлнэ, (3) `mosquitto`-гийн store-and-forward дараалал ирмэгээс холдож, Pi ↔ VM холбоо тасрахад ирмэг буфергүй болно. `cnc302/layer=edge` нь зорилгыг (ирмэгийн давхарга) илэрхийлнэ, `arch` нь техникийн нөхцөлийг — хоёулаа таарах ёстой.

---

## 4. Дүрсийг зөөврийн компьютер дээр барьж Pi руу импортлох

K3s нь Docker-ийн дүрсийн санг **харахгүй** — зангилаа бүр өөрийн containerd дүрсийн сантай ([Import Images](https://docs.k3s.io/add-ons/import-images)). `edge-agent`-ийн дүрс Docker Hub дээр байхгүй тул Pi-гийн containerd руу **tar-аар** оруулна.

**Яагаад Pi дээр `docker build` хийхгүй вэ:** Pi дээр барих нь Docker-ийг асааж (−60…−80 MiB), 1 GB дээр pip install-ийг 3–6 минут ажиллуулна. Docker Desktop нь *"supports running and building multi-platform images under emulation by default"* ба containerd image store-ийг анхдагчаар хэрэглэдэг ([Multi-platform builds](https://docs.docker.com/build/building/multi-platform/)) — тиймээс зөөврийн компьютер дээр arm64 дүрсийг шууд барина. Эмуляц нь удаан боловч numpy-д arm64 wheel бэлэн тул хөрвүүлэлт байхгүй.

```bash
# 💻 зөөврийн компьютер, репогийн үндсэнд
docker build --platform linux/arm64 -t cnc302/edge-agent:v1 edge/agent
docker image inspect cnc302/edge-agent:v1 --format '{{.Architecture}}'   # arm64
docker save --platform linux/arm64 -o edge-agent-v1-arm64.tar cnc302/edge-agent:v1
scp edge-agent-v1-arm64.tar cnc302@<pi-IP>:/tmp/
```

(`docker save --platform` нь API 1.48+ шаардана — [docker image save](https://docs.docker.com/reference/cli/docker/image/save/). Хуучин Docker дээр `--platform`-гүйгээр ажиллуул.)

```bash
# 🥧 Pi — хоёр аргын АЛЬ НЭГ нь
# (1) автомат импортын хавтас: tar-ыг K3s ажиллаж байхад ч тавьж болно,
#     "After a few seconds … available in the containerd image store"
sudo mkdir -p /var/lib/rancher/k3s/agent/images
sudo cp /tmp/edge-agent-v1-arm64.tar /var/lib/rancher/k3s/agent/images/
# (2) гараар:
# sudo k3s ctr images import /tmp/edge-agent-v1-arm64.tar

sudo k3s ctr images ls | grep edge-agent       # байгаа эсэхийг шалга
```

Анхаар: (1)-ийн хавтас дахь архив **k3s дахин эхлэх бүрд** дахин импортлогдоно (баримтад заасан), тиймээс том tar-ыг тэнд удаан үлдээвэл agent-ийн эхлэлт удаашрана.

`eclipse-mosquitto:2.0.22` ба `busybox:1.36` нь Docker Hub-ийн олон архитектуртай албан ёсны дүрс (arm64/v8 хувилбартай) — `imagePullPolicy: IfNotPresent` тул Pi өөрөө татна (Pi-д интернэт хэрэгтэй). Урьдчилан татах бол баримтын "online import": дүрсийн нэрсийг нэг мөрөнд нэгийг бичсэн `.txt` файлыг мөн хавтсанд тавина:

```bash
printf 'docker.io/library/eclipse-mosquitto:2.0.22\ndocker.io/library/busybox:1.36\n' \
  | sudo tee /var/lib/rancher/k3s/agent/images/cnc302-public.txt
```

> `edge-agent` нь `imagePullPolicy: Never` — kubelet хэзээ ч татахгүй. *"Pre-importing images onto the node is essential if you configure imagePullPolicy as Never"* (Import Images). Импорт хийгээгүй бол pod эхлэхгүй, шалтгаан нь `kubectl describe pod`-ийн Events-д гарна. `IfNotPresent` бол kubelet `docker.io/cnc302/edge-agent`-ийг Docker Hub-аас хайна — тэр нэрээр хэн нэгэн дүрс нийтэлбэл танихгүй код таны ирмэг дээр ажиллах эрсдэлтэй.

---

## 5. Байршуулах

```bash
# 🖥️ VM — репог VM дээр clone хийсэн, эсвэл lab08/k3s/-г scp-ээр хуулсан
cd ~/cnc302/lab08/k3s
nano 01-config.yaml            # ⚠ CLOUD_HOST = ЗӨӨВРИЙН КОМПЬЮТЕРИЙН LAN IP (VM-ийнх БИШ)
kubectl apply -f .
kubectl -n cnc302 get pods -o wide -w                      # NODE багана = Pi байх ЁСТОЙ
kubectl -n cnc302 logs deploy/mosquitto -c render-bridge   # гүүрний тохиргоо
kubectl -n cnc302 logs -f deploy/edge-agent
```

`kubectl logs/exec` нь VM-ээс Pi-гийн kubelet руу хандана. K3s-д agent server рүү **гарах** холболт тогтоож, kubelet-ийн урсгал тэр туннелээр явдаг (Requirements → Networking), харин metrics-server-т 10250 зангилаа хооронд шууд нээлттэй байх ёстой.

Ажиллаж байгааг **үүлний талаас** батал:

```bash
# 💻 зөөврийн компьютер
mosquitto_sub -h localhost -t 'cnc302/shutis/#' -v -C 10
mosquitto_sub -h localhost -t 'cnc302/shutis/mhts/lab/<DEVICE_ID>/bridge/state' -v -C 1   # 1 = холбогдсон
```

---

## 6. Хэмжих

```bash
# 🖥️ VM
kubectl top nodes
kubectl top pods -n cnc302
kubectl describe node <pi> | sed -n '/Capacity/,/System Info/p'       # Capacity ба Allocatable
kubectl describe node <pi> | sed -n '/Allocated resources/,/^Events/p'
kubectl get pods -A -o wide                                           # system pod-ууд аль зангилаанд
# 🥧 Pi
free -m
systemctl status k3s-agent --no-pager | grep -i memory                # k3s agent-ийн өөрийн санах ой
```

**Хүснэгт (тайланд):** үйлчилгээ бүрийн `requests` / `limits` / бодит RSS, мөн Лаб 1–7-ийн Compose дээрх ижил үйлчилгээний `docker stats` утга. Pi-гийн Allocatable-ийг MemTotal-тай харьцуулж, §2.2-ийн дүгнэлтийг **өөрийн тоогоор** батал эсвэл үгүйсгэ.

HPA-г ажиглах:
```bash
# 🖥️ VM
kubectl -n cnc302 get hpa edge-agent -w
# өөр терминалд — НЭГ pod-д CPU ачаалал:
kubectl -n cnc302 exec deploy/edge-agent -- sh -c 'while :; do :; done' &
# дууссаны дараа цэвэрлэх:
kubectl -n cnc302 rollout restart deploy/edge-agent
```

HPA-гийн тооцоо: `desiredReplicas = ceil(currentReplicas × currentMetricValue / desiredMetricValue)`, хэмжүүр нь pod-уудын **дундаж**, `Utilization` нь **requests-ийн хувь** ([HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/)). Нэг pod 800m (limit) иддэг бол `800/100 = 800 %` → HPA шууд `maxReplicas` руу үсэрнэ; шинэ хувиуд ачааллыг хуваалцахгүй тул дундаж буухгүй.

---

## 7. Pod `OOMKilled` эсвэл `Pending` болвол

Эхлээд **баримтыг цуглуул**:

```bash
# 🖥️ VM
kubectl -n cnc302 get pods -o wide                   # RESTARTS, NODE
kubectl -n cnc302 describe pod <pod> | grep -A3 "Last State"
#   Last State: Terminated,  Reason: OOMKilled,  Exit Code: 137
kubectl get events -n cnc302 --sort-by=.lastTimestamp | tail -20
# 🥧 Pi
dmesg -T | grep -i "killed process"                  # цөмийн OOM killer
vmstat 1 5                                           # si/so > 0 → swap идэвхтэй
```

**Шалтгаанаар нь** ялга:

| Шинж | Шалтгаан | Хийх зүйл |
|---|---|---|
| Exit 137, `Reason: OOMKilled` | контейнер өөрийн `limits.memory`-г давсан, эсвэл Pi бүхэлдээ санах ойгүй болсон | `INFER_THREADS=1`, `INTERVAL`-ыг өсгө; хувийн тоог бууруул |
| Pod `Pending`, `Insufficient memory` | Pi-гийн Allocatable-д `requests` багтахгүй | хувийн тоог бууруул, эсвэл `requests`-ээ бодит RSS-д ойртуул |
| Pod `Pending`, `didn't match Pod's node affinity/selector` | Pi-д `cnc302/layer=edge` шошго алга | §3.4(д) |
| Pod эхлэхгүй, Events-д дүрс татахгүй гэсэн мессеж | `edge-agent` дүрс Pi-д импортлогдоогүй (`Never`) | §4, `sudo k3s ctr images ls` |
| Pi `NotReady` | k3s-agent унасан / 6443 хүрэхгүй / VM-ийн IP өөрчлөгдсөн | 🥧 `journalctl -u k3s-agent -n 50`; `curl -k https://<VM-IP>:6443` |
| `kubectl top` дээр Pi алга | 10250/tcp хаалттай | §3.3 |
| `edge-agent` лог: `mosquitto` нэр шийдэгдэхгүй | 8472/udp хаалттай — Pi-гийн pod VM дээрх coredns-д хүрэхгүй | §3.3 |
| Compose ба K3s-ийн гүүр ээлжилж тасарна | Compose-ийн mosquitto зогсоогүй (ижил ClientID) | §3.4(в) |

**Гол зарчим:** `limits`-ийг ӨСГӨХ нь үргэлж зөв шийдэл БИШ. 1 GB дээр хамгийн зөв хариулт нь ихэвчлэн "энэ ажлыг Pi дээр биш, үүлэн дээр ажиллуул" байдаг — Лаб 8-ын гол сургамж яг энэ.

---

## 8. Compose ба Kubernetes-ийн харьцуулалт

| Ойлголт | Docker Compose (`edge/`) | Kubernetes (энэ фолдер) |
|---|---|---|
| Үйлчилгээ | `services:` | Deployment + Service |
| Хаана ажиллах | ганц хост | `nodeSelector` (шошго) |
| Боть | `volumes:` | PersistentVolumeClaim (`local-path`) |
| Орчны хувьсагч | `.env` + `environment:` | ConfigMap / Secret |
| Тохиргооны файл | bind mount | ConfigMap + `subPath` |
| Загвар орлуулах | `make bridge` (host дээр `sed`) | `initContainer` + `sed` |
| Эрүүл мэнд | `healthcheck:` | readinessProbe / livenessProbe |
| Нөөцийн хязгаар | `deploy.resources.limits` | `resources.requests` **ба** `limits` |
| Дахин эхлүүлэх | `restart:` | ReplicaSet (автоматаар) |
| Порт нээх | `ports:` | NodePort (бүх зангилаа дээр) |
| Өргөтгөх | гараар `--scale` | `replicas` эсвэл HPA |
| Дүрс | `build:` тухайн хост дээр | зангилаа бүрийн containerd-д татах/импортлох |

**`requests` ба `limits`-ийн ялгаа чухал:** *"the scheduler ensures that, for each resource type, the sum of the resource requests of the scheduled containers is less than the capacity of the node"*; санах ойн limit давбал *"the Linux kernel out-of-memory subsystem activates"* ([Resource Management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)). Compose-д зөвхөн хана байдаг — тиймээс Compose нь "багтах уу, үгүй юу"-г УРЬДЧИЛАН хэлж чадахгүй. Гэхдээ §2.2-оос харахад Kubernetes-ийн "урьдчилсан" хариу ч **reserved тохируулаагүй** бол хуурамч итгэл өгнө.

---

## 9. Устгах / буцаах

```bash
# 🖥️ VM
kubectl delete -f .
kubectl delete namespace cnc302                 # PVC-тэй хамт — өгөгдөл алдагдана!
kubectl delete node <pi>                        # Pi-г дахин нэгтгэх бол ЗААВАЛ (node password secret)

# 🥧 Pi — agent-ийг устгаж Compose руу буцах
sudo /usr/local/bin/k3s-agent-uninstall.sh
sudo systemctl start docker && cd ~/cnc302/edge && make up

# 🖥️ VM — server-ийг бүрэн устгах (заавал биш)
sudo /usr/local/bin/k3s-uninstall.sh
```

Скриптийн нэрс ба `delete node` шаардлага — [Uninstalling K3s](https://docs.k3s.io/installation/uninstall).

---

## 10. Эх сурвалж

Энэ файлын бүх баримтын жагсаалтыг `lab08/README.md` §9-өөс үз. Хамгийн чухал нь: [K3s Requirements](https://docs.k3s.io/installation/requirements), [K3s Quick-Start](https://docs.k3s.io/quick-start), [Import Images](https://docs.k3s.io/add-ons/import-images), [Resource Profiling](https://docs.k3s.io/reference/resource-profiling), [Well-Known Labels](https://kubernetes.io/docs/reference/labels-annotations-taints/), [HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/), [VirtualBox Networking](https://www.virtualbox.org/manual/topics/networkingdetails.html) (бүгд 2026-09-д хандсан).
