# Түгээмэл алдаа ба шийдэл

## Docker ба стек

| Алдаа | Шалтгаан | Шийдэл |
|---|---|---|
| `no space left on device` | дүрс, лог, боть хуримтлагдсан | `docker system df` → `docker system prune -a` (боть хэвээр үлдэнэ) |
| `port is already allocated` | өөр процесс портыг эзэлсэн | `sudo ss -tlnp \| grep <порт>` |
| Контейнер `Restarting` давтана | OOM эсвэл тохиргооны алдаа | `docker inspect <нэр> \| grep -i oomkilled`; логийг үз |
| `exec format error` | дүрс arm64-д зориулагдаагүй | `docker manifest inspect <image> \| grep arm64` |
| `docker stats` санах ойг 0 гэнэ | cgroup memory идэвхгүй | SETUP Б.4 |
| Compose `.env` уншихгүй | `.env` файл `stack/` дотор биш | `docker compose config \| head` |

## ThingsBoard

| Алдаа | Шийдэл |
|---|---|
| 3 минутаас удаан эхэлнэ | Pi дээр хэвийн. `start_period: 180s` |
| `OOMKilled` | swap 2 GB эсэхийг шалга; `JAVA_OPTS` дахь `-Xmx`-ийг 1200m болго |
| REST 401 | нууц үг солигдсон эсвэл токен хуучирсан |
| MQTT холбогдохгүй | ThingsBoard-ын MQTT нь **1884** порт (EMQX 1883) |
| Firmware төхөөрөмжид хүрэхгүй | Device → Manage firmware → багцыг оноох |

## EMQX

| Алдаа | Шийдэл |
|---|---|
| TLS `unknown ca` | `--ca` буруу эсвэл сертификат өөр CA-гаас |
| TLS `hostname mismatch` | серверийн CN нь Pi-гийн нэртэй таарахгүй |
| Холболт 10000 дээр зогсоно | `EMQX_LISTENERS__TCP__DEFAULT__MAX_CONNECTIONS` |
| Самбарт нэвтрэхгүй | `.env` дэх `EMQX_DASHBOARD_PASSWORD`; эхний эхлэлтийн дараа зөвхөн самбараас солино |

## InfluxDB 3 Core

InfluxDB 3 Core-ийн CLI түргэн өөрчлөгддөг. Хэрэв `--without-auth` эсвэл `--object-store` таних тэмдэг ажиллахгүй бол:

```bash
docker run --rm influxdb:3.2-core influxdb3 serve --help
```

Шийдэгдэхгүй бол InfluxDB 2.7 руу шилжинэ:
```bash
docker compose -f docker-compose.yml -f docker-compose.influx2.yml --profile core up -d
```
Энэ тохиолдолд Grafana-гийн өгөгдлийн эх сурвалж (SQL биш Flux), Node-RED-ийн бичих зангилаа өөр болно — `lab05/reference/influx2/` дотор бэлэн хувилбар байгаа.

## Сүлжээ ба холболт

| Алдаа | Шийдэл |
|---|---|
| `pi-team03.local` олдохгүй | mDNS ажиллахгүй байна — IP хаягаар хандана (`hostname -I`) |
| Хөтөч холбогдохгүй | VS Code PORTS таб эсвэл `ssh -L` туннел |
| MQTT `Connection refused` | Pi дээр брокер ажиллаж байна уу: `docker compose ps` |
| Гэнэт тасалдана | Wi-Fi эрчим хүч хэмнэх горим: `sudo iw wlan0 set power_save off` |

## Хэмжилтийн чанар

- Хэмжилтийн өмнө **бусад ачааллыг зогсооно** (`htop`-оор шалга)
- Гурваас доошгүй удаа давтаж дунджийг авна
- `vcgencmd get_throttled` нь `0x0` биш бол хэмжилтийг хүчингүй гэж үз
- Цагийн синхрончлолгүй бол саатлын хэмжилт утгагүй (`timedatectl status`)
