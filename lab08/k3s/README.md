# K3s манифестууд — Лаб 8 (Raspberry Pi 3B, 1 GB)

XIV долоо хоногийн бие даалтаар эдгээрийг **УНШИЖ ойлгосон** байх ёстой.

## Юуг хаана ажиллуулах вэ

| Давхарга | Төмөр | Юу ажиллах вэ |
|---|---|---|
| Ирмэг | **Raspberry Pi 3B** (K3s) | mosquitto (гүүр) + edge-agent |
| Үүл | зөөврийн компьютер (Docker Compose) | EMQX, InfluxDB, Grafana, registry, Node-RED, Dex, GraphQL, Ollama |

> **EMQX/InfluxDB/Grafana-г Pi-гийн K3s рүү оруулах гэж бүү оролд.** Зөвхөн
> InfluxDB 3 нь 250–500 MiB, EMQX 150–250 MiB иддэг. K3s өөрөө ~400 MiB
> авсны дараа 1 GB-д тэдгээр багтахгүй — pod нь `OOMKilled` эсвэл
> `Pending` болно. Энэ нь алдаа биш, **тоо ярьж байна**.

## Файлууд

| Файл | Агуулга |
|---|---|
| `00-namespace.yaml` | `cnc302` нэрийн орон зай |
| `01-config.yaml` | ConfigMap (UNS + `CLOUD_HOST`) + Secret загвар |
| `10-mosquitto.yaml` | ConfigMap (mosquitto.conf + гүүрний загвар) + PVC + Deployment + NodePort Service |
| `20-edge-agent.yaml` | Deployment (локал импортолсон дүрс) |
| `90-hpa.yaml` | HPA — ба яагаад ганц зангилаа дээр 1→2-оос цааш явахгүй нь |

---

## 1. Санах ойн тооцоо (ЭНЭ ХЭСГИЙГ АЛГАСАЖ БОЛОХГҮЙ)

```
Pi 3B-гийн нийт RAM                            1024 MiB
  − GPU-д хуваарилсан (gpu_mem=64)              −64 MiB
  − firmware / kernel-ийн эзэмшил               −35 MiB
  ────────────────────────────────────────────────────
  MemTotal (free -m харуулах утга)            ≈ 925 MiB
  − Raspberry Pi OS Lite (systemd, sshd, …)     −45 MiB
  ────────────────────────────────────────────────────
  БОЛОМЖТОЙ                                   ≈ 880 MiB
```

Үүнээс:

| Хэрэглэгч | Бодит RSS | Тэмдэглэл |
|---|---:|---|
| k3s server (apiserver + kubelet + containerd + sqlite) | **~400 MiB** | pod биш, systemd үйлчилгээ — `requests`-д ОРОХГҮЙ |
| coredns | ~25 MiB | request 70Mi (k3s-ийн анхны утга) |
| metrics-server | ~25 MiB | HPA-д ЗААВАЛ хэрэгтэй |
| local-path-provisioner | ~10 MiB | PVC-г microSD дээр үүсгэнэ |
| **mosquitto** (манай) | ~12 MiB | request 32Mi / limit 96Mi |
| **edge-agent** (манай) | ~55–110 MiB | request 96Mi / limit 160Mi |
| **Нийт (1 агент)** | **≈ 530 MiB** | ~350 MiB нөөц үлдэнэ |
| **Нийт (HPA 2 агент)** | **≈ 600 MiB** | ~280 MiB нөөц — ЭНЭ Л ХЯЗГААР |

Товлогчийн (scheduler) тал дээрх тооцоо өөр байдгийг анзаар:

```
allocatable ≈ MemTotal − eviction threshold (100Mi) ≈ 825 MiB
хүсэлтүүд (requests): coredns 70 + metrics-server 70 + mosquitto 32
                      + edge-agent 96 × N
  N = 1 → 268 Mi     N = 2 → 364 Mi     N = 3 → 460 Mi
```

`requests`-ийн хувьд 3 хувь ч "багтана", **гэвч бодит RSS багтахгүй** —
яг үүнээс болж 3 дахь pod нь Pending биш, `OOMKilled` болж эхэлдэг.
`requests` бол амлалт, `limits` бол хана, **RSS бол үнэн**. Гурвыг нь
`kubectl top` + `free -m`-ээр зэрэг хэмжиж тайландаа бич.

---

## 2. K3s суулгах (нэг удаа, Pi 3B дээр)

**Эхлээд Pi дээрх Docker Compose-ыг БҮРЭН зогсооно** — эс тэгвээс хоёулаа
нэг санах ойг булаацалдана:

```bash
cd ~/cnc302/edge && docker compose down
docker ps                      # хоосон байх ёстой
free -m                        # 800+ MiB сул байх ёстой
```

Swap-г 1 GB болгож нэмбэл ачаалалтай үед аврах боловч microSD-г элээнэ:

```bash
sudo dphys-swapfile swapoff
sudo sed -i 's/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=1024/' /etc/dphys-swapfile
sudo dphys-swapfile setup && sudo dphys-swapfile swapon
```

Суулгалт:

```bash
curl -sfL https://get.k3s.io | sh -s - \
  --write-kubeconfig-mode 644 \
  --disable traefik \
  --disable servicelb
```

- `--disable traefik` → Ingress контроллер ~60 MiB иднэ, бидэнд MQTT
  (TCP) хэрэгтэй болохоос HTTP Ingress хэрэггүй.
- `--disable servicelb` → LoadBalancer төрлийн Service ашиглахгүй,
  NodePort хангалттай (~15 MiB хэмнэнэ).
- **metrics-server-ийг УНТРААХГҮЙ** — HPA түүнгүйгээр ажиллахгүй.

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl get nodes                 # Ready болтол 1–3 минут (microSD удаан)
kubectl top nodes                 # metrics-server бэлэн эсэх
```

---

## 3. Дүрсийг Pi дээр барьж импортлох

K3s нь Docker-ын дүрсийн санг ХАРАХГҮЙ (өөрийн containerd-тэй). Тиймээс:

```bash
cd ~/cnc302/edge/agent
docker build -t cnc302/edge-agent:v1 .              # Pi 3B дээр 3–6 минут
docker save cnc302/edge-agent:v1 | sudo k3s ctr images import -
sudo k3s ctr images ls | grep edge-agent            # байгаа эсэхийг шалга
```

`docker` байхгүй бол шууд tar-аар:
```bash
sudo k3s ctr images import cnc302-edge-agent-v1.tar
```

Мөн `busybox:1.36` (initContainer) хэрэгтэй. Интернэт байвал автоматаар
татагдана, үгүй бол урьдчилан импортлоно:

```bash
sudo k3s ctr images pull docker.io/library/busybox:1.36
sudo k3s ctr images pull docker.io/library/eclipse-mosquitto:2.0.20
```

> `imagePullPolicy: IfNotPresent` нь энэ бүх ажлын үндэс. `Always` болговол
> K3s Docker Hub-аас `cnc302/edge-agent` хайж олохгүй → `ErrImagePull`.

---

## 4. Байршуулах

```bash
cd ~/cnc302/lab08/k3s
# ⚠ 01-config.yaml дотор CLOUD_HOST-ыг компьютерийнхээ LAN IP болгож солино!
kubectl apply -f .

kubectl -n cnc302 get pods -w
kubectl -n cnc302 logs deploy/mosquitto -c render-bridge   # гүүрний тохиргоо
kubectl -n cnc302 logs -f deploy/edge-agent
```

Ажиллаж байгаа эсэхийг **үүлний талаас** батал:

```bash
# зөөврийн компьютер дээр
mosquitto_sub -h localhost -t 'cnc302/shutis/#' -v -C 10
```

Гүүрний төлөв:
```bash
mosquitto_sub -h localhost -t 'cnc302/shutis/mhts/lab/pi3b-01/bridge/state' -v
# 1 = холбогдсон, 0 = тасарсан
```

---

## 5. Хэмжих

```bash
kubectl top nodes
kubectl top pods -n cnc302
free -m                                   # kubectl top-той харьцуул
kubectl -n cnc302 describe node | sed -n '/Allocated resources/,/^Events/p'
```

**Хүснэгт (тайланд):** үйлчилгээ бүрийн `requests` / `limits` / бодит RSS,
мөн Compose дээрх ижил үйлчилгээний `docker stats` утга. Ялгааг тайлбарла.

HPA-г ажиглах:
```bash
kubectl -n cnc302 get hpa edge-agent -w
# өөр терминалд ачаалал үүсгэ:
kubectl -n cnc302 exec deploy/edge-agent -- python -c "
while True: pass" &
```

---

## 6. Pod нь OOMKilled болвол юу хийх вэ

Эхлээд **баримтыг цуглуул** (тайланд хэрэгтэй):

```bash
kubectl -n cnc302 get pods                       # RESTARTS багана
kubectl -n cnc302 describe pod <pod> | grep -A3 "Last State"
#   Last State: Terminated,  Reason: OOMKilled,  Exit Code: 137
kubectl get events -n cnc302 --sort-by=.lastTimestamp | tail -20
dmesg -T | grep -i "killed process"              # kernel-ийн OOM killer
```

Дараа нь **шалтгаанаар нь** ялга:

| Шинж | Шалтгаан | Хийх зүйл |
|---|---|---|
| Exit 137, `Reason: OOMKilled` | контейнер өөрийн `limits`-ээ давсан | `limits.memory`-г 32–64Mi-аар нэм, ЭСВЭЛ ажлыг хөнгөл (жишээ: `INFER_THREADS=1`, `INTERVAL`-ыг өсгө) |
| Pod `Pending`, `Insufficient memory` | зангилаанд `requests` багтахгүй | хувийн тоог бууруул, эсвэл `requests`-ээ бодит RSS-д ойртуул |
| Зангилаа өөрөө `NotReady`, k3s унтарсан | системийн OOM killer k3s-ийг алсан | Compose зогссон эсэхийг шалга, swap нэм, `--disable`-уудыг батал |
| Байнгын CrashLoopBackOff | дүрс буруу архитектур / импортлоогүй | `sudo k3s ctr images ls`, дүрсийг Pi дээр дахин бари |

**Гол зарчим:** `limits`-ийг ӨСГӨХ нь үргэлж зөв шийдэл БИШ. 1 GB дээр
хамгийн зөв хариулт нь ихэвчлэн "энэ ажлыг Pi дээр биш, үүлэн дээр
ажиллуул" байдаг — Лаб 8-ын гол сургамж яг энэ.

---

## 7. Compose ба Kubernetes-ийн харьцуулалт

| Ойлголт | Docker Compose (`edge/`) | Kubernetes (энэ фолдер) |
|---|---|---|
| Үйлчилгээ | `services:` | Deployment + Service |
| Боть | `volumes:` | PersistentVolumeClaim (`local-path`) |
| Орчны хувьсагч | `.env` + `environment:` | ConfigMap / Secret |
| Тохиргооны файл | bind mount | ConfigMap + `subPath` |
| Загвар орлуулах | `make bridge` (host дээр `sed`) | `initContainer` + `sed` |
| Эрүүл мэнд | `healthcheck:` | readinessProbe / livenessProbe |
| Нөөцийн хязгаар | `deploy.resources.limits` | `resources.requests` **ба** `limits` |
| Дахин эхлүүлэх | `restart:` | ReplicaSet (автоматаар) |
| Порт нээх | `ports:` | NodePort |
| Өргөтгөх | гараар `--scale` | `replicas` эсвэл HPA |

**`requests` ба `limits`-ийн ялгаа чухал:** `requests` нь товлогчид "энэ
pod-д хамгийн багадаа ийм нөөц хэрэгтэй" гэж хэлнэ (товлолт үүгээр
шийдэгдэнэ); `limits` нь дээд хана (давбал OOMKilled). Compose-д зөвхөн
хана байдаг — тиймээс Compose нь "багтах уу, үгүй юу"-г УРЬДЧИЛАН хэлж
чадахгүй, зөвхөн унасны дараа мэдэгддэг.

---

## 8. Устгах / буцаах

```bash
kubectl delete -f .
kubectl delete namespace cnc302        # PVC-тэй хамт — өгөгдөл алдагдана!

# K3s-ийг бүрэн устгаж Compose руу буцах
sudo /usr/local/bin/k3s-uninstall.sh
cd ~/cnc302/edge && make up
```
