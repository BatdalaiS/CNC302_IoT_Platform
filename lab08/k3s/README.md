# K3s манифестууд — Лаб 8

XIV долоо хоногийн бие даалтаар эдгээрийг УНШИЖ ойлгосон байх ёстой.

## Файлууд

| Файл | Агуулга |
|---|---|
| `00-namespace.yaml` | тусгаарлагдсан нэрийн орон зай |
| `01-config.yaml` | ConfigMap + Secret |
| `10-emqx.yaml` | Deployment + PVC + NodePort Service |
| `20-influxdb.yaml` | Deployment + PVC + ClusterIP Service |
| `30-grafana.yaml` | Deployment + PVC + NodePort Service |
| `90-hpa.yaml` | хэвтээ автомат өргөтгөл (сонголт) |

## Ажиллуулах

```bash
# 1. Docker Compose стекийг ЗОГСООНО (санах ой хуваалцахгүй)
cd ~/cnc302/stack && docker compose --profile core --profile pipeline down

# 2. K3s суулгах (нэг удаа)
curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl get nodes

# 3. Байршуулах
cd ~/cnc302/lab08/k3s
# ⚠ 01-config.yaml дотор нууц үгээ солино!
kubectl apply -f .

# 4. Ажиглах
kubectl -n cnc302 get pods -w
kubectl -n cnc302 describe pod <нэр>
kubectl -n cnc302 logs -f deploy/emqx
```

## Хандах

| Үйлчилгээ | Хаяг |
|---|---|
| EMQX MQTT | `<pi>:31883` |
| EMQX самбар | `http://<pi>:31083` |
| Grafana | `http://<pi>:30300` |
| InfluxDB | зөвхөн кластер дотроос (`influxdb:8181`) |

## Compose ба Kubernetes-ийн харьцуулалт

| Ойлголт | Docker Compose | Kubernetes |
|---|---|---|
| Үйлчилгээ | `services:` | Deployment + Service |
| Боть | `volumes:` | PersistentVolumeClaim |
| Орчны хувьсагч | `environment:` | ConfigMap / Secret |
| Эрүүл мэнд | `healthcheck:` | readinessProbe / livenessProbe |
| Нөөцийн хязгаар | `deploy.resources` | `resources.requests/limits` |
| Дахин эхлүүлэх | `restart:` | ReplicaSet (автоматаар) |
| Порт нээх | `ports:` | NodePort / Ingress |
| Өргөтгөх | гараар `--scale` | `replicas` эсвэл HPA |

**`requests` ба `limits`-ийн ялгаа чухал:** `requests` нь товлогчид (scheduler)
"энэ pod-д хамгийн багадаа ийм нөөц хэрэгтэй" гэж хэлнэ; `limits` нь дээд
хязгаар. Compose-д зөвхөн limits байдаг — тиймээс Kubernetes нөөцийг илүү
ухаалаг хуваарилдаг.

## Устгах

```bash
kubectl delete -f .
# бүрэн устгах (PVC-тэй хамт өгөгдөл алдагдана!)
kubectl delete namespace cnc302
```
