# Лаб 2 — Төхөөрөмжийн бүрэн амьдралын мөчлөг ба OTA

| | |
|---|---|
| **7 хоног** | V |
| **Хугацаа** | 4 цаг |
| **Суралцахуйн үр дүн** | ҮД4 (аюулгүй төхөөрөмж, өгөгдлийн удирдлага) |
| **Үнэлгээ** | Бичгийн тайлан, 10 оноо |
| **Гол хэмжилт** | Бүртгэлийн хурд, OTA-гийн хугацаа ба амжилтын хувь |

---

## 1. Зорилго

Төхөөрөмжийн амьдралын мөчлөгийн **дөрвөн үе шатыг** өөрсдөө хэрэгжүүлж, хэмжинэ:

```
бүртгэл (provisioning) → таних тэмдэг (identity) → OTA шинэчлэлт → хүчингүй болгох (revocation)
```

Худалдааны платформууд (ThingsBoard, AWS IoT, Azure IoT Hub) эдгээрийг **хар хайрцаг** болгож нуудаг. Энэ лабораторид та `lab02/registry/app.py` (≈500 мөр) ба `lab02/ota_agent.py` (≈270 мөр) хоёрыг **уншиж, ажиллуулж, эвдэж** протоколыг ил харна.

> **Яагаад ThingsBoard биш вэ:** ThingsBoard-ын албан ёсны заавар хөгжүүлэлт/PoC-д хүртэл 4 GB RAM шаарддаг. Pi 3B-д нийт 1 GB (OS-д ~925 MiB). Гэхдээ илүү чухал шалтгаан бий — та энэ хичээлээр *платформ ашиглагч* биш *платформ зохиогч* болох ёстой. Лабораторийн эцэст сонголтот харьцуулалт хийнэ (§4, Алхам 8).

---

## 2. Урьдчилсан нөхцөл

- Лаб 1 дууссан, `lab01-done` tag тавигдсан
- 💻 `cd stack && make up && make health` → бүх мөр 200
- 🥧 `cd edge && make up && make link` → `bridge/state 1`
- Бие даалт IV: X.509 сертификатын гинжин хэлхээ (CA → төхөөрөмж) уншсан

```bash
# 💻 бүртгэлийн үйлчилгээ ажиллаж байгаа эсэх
curl -s localhost:8090/health | jq
# → {"ok": true, "devices": 0, "mqtt": true}
```

---

## 3. Онолын сануулга

### Bulk vs JIT — хоёр загварын солилцоо

| | **Bulk (бөөнөөр)** | **JIT (яг цагт нь)** |
|---|---|---|
| Хэзээ бүртгэнэ | үйлдвэрээс гарахаас өмнө | төхөөрөмж анх залгагдахад |
| Нэвтрэлт хаанаас | урьдчилан үүсгэж бүтээгдэхүүнд суулгана | төхөөрөмж өөрөө гуйна |
| Давуу тал | хяналттай, аудит хийхэд амархан | ашиглагдаагүй бүртгэл үлдэхгүй |
| Сул тал | 10 000 бүртгэлээс 3 000 нь хэзээ ч ашиглагдахгүй | **хэн болохыг батлах** асуудал хурцаар тавигдана |
| Хэзээ хэрэглэх | хаалттай флот, тодорхой тоо | нээлттэй тархалт, тодорхойгүй тоо |

JIT-ийн гол эрсдэл: баталгаагүй бол **хэн ч** `device_id` сонгоод флотод нэвтэрч болно. Шийдэл нь үйлдвэрт суусан X.509 сертификат — үүнийг Алхам 3-т хийнэ.

### Таних тэмдгийн гурван түвшин

| Түвшин | Механизм | Хулгайлагдвал | Хэрэглээ |
|---|---|---|---|
| 1 | нэр/нууц үг | бүх флот эрсдэлд | зөвхөн лаборатори |
| 2 | төхөөрөмж тус бүрийн токен | нэг төхөөрөмж | дунд зэрэг |
| 3 | **X.509 + mTLS** | нэг төхөөрөмж, CRL-ээр хаана | үйлдвэрлэл |

### OTA-гийн протокол — CNC302 хувилбар

```
сервер → төхөөрөмж   .../ota/offer     {fw_id, version, size, sha256, chunk_size, chunks}
төхөөрөмж → сервер   .../ota/request   {fw_id, chunk: N}
сервер → төхөөрөмж   .../ota/chunk/N   <хоёртын 4 KiB>
төхөөрөмж → сервер   .../ota/state     {state, progress, error}
```

![Зураг 2.1 — OTA-гийн төлөвийн машин ба MQTT мессежийн дараалал (offer → request → chunk/N → state)](../docs/img/fig-ota-states.svg)

Төлөвийн дараалал:
```
DOWNLOADING → DOWNLOADED → VERIFIED → UPDATING → UPDATED
                               ↓            ↓
                            FAILED     ROLLED_BACK
```

**Гурван зүйл заавал байх ёстой**, эс бөгөөс OTA нь тоосго үйлдвэрлэх машин болно:

1. **Шалгах (checksum).** Татсан файл эвдэрсэн эсэхийг суулгахаас ӨМНӨ шалгана.
2. **Буцаах (rollback).** Шинэ хувилбар ачаалагдахгүй бол хуучинд буцна. Тиймээс A/B хуваалт эсвэл нөөц хуулбар хэрэгтэй.
3. **Canary.** 5 000 төхөөрөмжийг нэг дор шинэчилж эвдвэл засах арга байхгүй. Эхлээд 5–20%-д, амжилттай бол бусдад.

---

## 4. Алхмууд

### Алхам 0 — EMQX REST API түлхүүр ба authenticator (15 мин) 💻

`registry` нь EMQX-ийн REST API-г (`/api/v5`) дуудаж төхөөрөмж бүрд MQTT нэвтрэлт үүсгэнэ. REST API нь **самбарын admin нууц үгийг хүлээн авдаггүй** (EMQX 5.0-оос хойш) — зөвхөн API key / secret key-г HTTP Basic нэвтрэлтээр хүлээн авна.

1. http://localhost:18083 → **System → API Key → + Create** → Expire At хоосон → **Confirm**. Secret key-г **тэр дор нь** хуулж ав — дахин харагдахгүй.
2. `stack/.env`-д бичээд `registry`-г шинэ утгатай нь дахин үүсгэ:
   ```bash
   cd ~/cnc302/stack
   nano .env                         # EMQX_API_KEY=…  EMQX_API_SECRET=…
   docker compose --profile core up -d registry
   export EMQX_API_KEY=$(grep '^EMQX_API_KEY=' .env | cut -d= -f2)
   export EMQX_API_SECRET=$(grep '^EMQX_API_SECRET=' .env | cut -d= -f2)
   curl -s -u "$EMQX_API_KEY:$EMQX_API_SECRET" localhost:18083/api/v5/nodes | jq '.[0].version'
   # → "5.8.6"
   ```
3. **Built-in database** authenticator-ыг **идэвхгүй** (`"enable": false`) байдлаар үүсгэнэ. Үүсгээгүй бол хэрэглэгч нэмэх дуудлага `404 Authenticator not found` буцаана. Идэвхгүй үед ч хэрэглэгч нэмэх боломжтой; харин EMQX нээлттэй хэвээр үлдэж, гүүр ба бусад клиент тасрахгүй. Алхам 7-д л идэвхжүүлнэ.
   ```bash
   curl -s -u "$EMQX_API_KEY:$EMQX_API_SECRET" -X POST localhost:18083/api/v5/authentication \
     -H 'content-type: application/json' \
     -d '{"mechanism":"password_based","backend":"built_in_database",
          "user_id_type":"username",
          "password_hash_algorithm":{"name":"sha256","salt_position":"suffix"},
          "enable":false}' | jq '.id, .enable'
   # → "password_based:built_in_database"  false
   ```

> ⚠ EMQX-ийн баримтаар authenticator идэвхтэй үед нэвтрэлтийн мэдээлэл нь олдоогүй клиент (сүүлийн authenticator дээр) **татгалзагдана** — нэр/нууц үггүй бүх клиент ч мөн адил. Иймээс authenticator-ыг зөвхөн Алхам 7-д богино хугацаанд асаана.
>
> Албан ёсны баримт: [EMQX REST API](https://docs.emqx.com/en/emqx/v5.8/guides/api.html) · [API Keys](https://docs.emqx.com/en/emqx/v5.8/guides/api-keys.html) · [Authentication](https://docs.emqx.com/en/emqx/v5.8/guides/access-control/authn/authn.html) · [Built-in Database](https://docs.emqx.com/en/emqx/v5.8/guides/access-control/authn/mnesia.html)

---

### Алхам 1 — Bulk бүртгэл ба хурдны хэмжилт (30 мин) 💻

```bash
cd ~/cnc302/lab02
python3 provision.py bulk --count 10  --out out/devices.csv
python3 provision.py bulk --count 100 --prefix b100 --out out/b100.csv
python3 provision.py bulk --count 500 --prefix b500 --out out/b500.csv
python3 provision.py list --limit 10
```

#### Хүснэгт 2.1 — Bulk бүртгэлийн хурд

| Төхөөрөмжийн тоо | Нийт хугацаа (сек) | мс/төхөөрөмж | Тэмдэглэл |
|---|---|---|---|
| 10 | | | |
| 100 | | | |
| 500 | | | |

> Хугацаа **шугаман** өсөж байна уу? Үгүй бол хаана бөглөрч байна вэ? (Санамж: `app.py`-ийн `bulk()` бүх INSERT-ийг НЭГ transaction-д хийдэг, харин төхөөрөмж бүрд EMQX руу нэг HTTP дуудлага (`emqx_add_user`) явуулдаг. `EMQX_API_KEY`-гүйгээр ажиллуулж харьцуул.)
>
> `devices.csv`-ийн `emqx` багана `created` байх ёстой. `skipped` бол Алхам 0-ийн 2-р хэсэг, `error 404` бол 3-р хэсэг хийгдээгүй.

⚠ `out/devices.csv` нь нууц үг агуулна. `.gitignore`-д байгааг батал:
```bash
git check-ignore -v lab02/out/devices.csv    # мөр буцаах ЁСТОЙ
```

---

### Алхам 2 — JIT бүртгэл ба түүний эмзэг байдал (20 мин) 💻

```bash
python3 provision.py jit --device-id pi3b-01
python3 provision.py jit --device-id pi3b-01      # хоёр дахь удаа юу болох вэ?
```

Одоо **халдлагыг дуурай**:
```bash
python3 provision.py jit --device-id ямар-ч-нэр-бичиж-болно
python3 provision.py list --limit 20
```

#### Хүснэгт 2.2 — Bulk vs JIT харьцуулалт

| Шалгуур | Bulk | JIT | Таны төслийн сонголт |
|---|---|---|---|
| Нэг төхөөрөмжийн хугацаа (мс) | | | |
| Урьдчилан хэдэн бүртгэл шаардлагатай | | | |
| Баталгаажуулалт байгаа юу | | | |
| Хүчингүй болгоход яах вэ | | | |

---

### Алхам 3 — X.509 таних тэмдэг ба mTLS (50 мин) 💻🥧

Өөрсдийн CA үүсгэж, төхөөрөмжид сертификат олгоно. Брокерийн (EMQX) сертификат нь **зөөврийн компьютерт** зориулагдана: клиент холбогдсон хаягаа сертификатын subjectAltName (SAN)-тай тулгадаг тул Pi-гаас холбогдох LAN IP (`CLOUD_HOST`) SAN-д заавал орно.

```bash
# 💻 компьютер дээр
cd ~/cnc302/lab02
CLOUD_HOST=<компьютерийн LAN IP> ./make_certs.sh init   # CA + брокерийн сертификат
./make_certs.sh device pi3b-01
./make_certs.sh device dev0001
./make_certs.sh list

# Гинжин хэлхээг батлах
openssl verify -CAfile certs/ca.crt certs/server.crt certs/pi3b-01.crt   # → OK, OK
openssl x509 -in certs/server.crt -noout -ext subjectAltName              # CLOUD_HOST байгаа юу?
openssl x509 -in certs/pi3b-01.crt -noout -subject -dates -ext extendedKeyUsage
```

> Албан ёсны баримт: [openssl-req](https://docs.openssl.org/3.0/man1/openssl-req/) · [openssl-x509](https://docs.openssl.org/3.0/man1/openssl-x509/) · [openssl-verify](https://docs.openssl.org/3.0/man1/openssl-verify/) · [x509v3_config (subjectAltName, extendedKeyUsage)](https://docs.openssl.org/3.0/man5/x509v3_config/)

EMQX-д mTLS сонсогчийг асаана. SSL сонсогч (8883) анхдагчаар **нэг талын** TLS: клиентийн сертификатыг шаарддаггүй. Хоёр талын (mTLS) болгохын тулд `ssl_options.verify = verify_peer` ба `ssl_options.fail_if_no_peer_cert = true` хоёулаа хэрэгтэй. `stack/docker-compose.yml` эдгээрийг `EMQX_LISTENERS__SSL__DEFAULT__SSL_OPTIONS__…` орчны хувьсагчаар (`.` → `__`, угтвар `EMQX_`) аль хэдийн тохируулсан; `EMQX_TLS_ENABLE` нь сонсогчийг асаана:

```bash
cd ~/cnc302/stack
cp ../lab02/certs/{ca.crt,server.crt,server.key} emqx/certs/
sed -i 's/^EMQX_TLS_ENABLE=.*/EMQX_TLS_ENABLE=true/' .env
docker compose --profile core up -d emqx          # орчны хувьсагч өөрчлөгдсөн тул контейнер дахин үүснэ
docker compose exec emqx emqx ctl listeners | grep -A3 'ssl:default'   # running: true
curl -s -u "$EMQX_API_KEY:$EMQX_API_SECRET" localhost:18083/api/v5/listeners/ssl:default \
  | jq '.ssl_options | {verify, fail_if_no_peer_cert}'
# → {"verify":"verify_peer","fail_if_no_peer_cert":true}
```

> Логт `cert_file_not_found` эсвэл permission алдаа гарвал: Linux хост дээр `server.key` нь зөвхөн таны хэрэглэгчид уншигдах (600) тул контейнер доторх `emqx` хэрэглэгч уншиж чадахгүй байж болно. Зөвхөн лабораторид: `chmod 644 emqx/certs/server.key`.
>
> Албан ёсны баримт: [EMQX — Enable SSL/TLS Connection](https://docs.emqx.com/en/emqx/v5.8/guides/network/emqx-mqtt-tls.html) · [EMQX — Configuration (environment variables)](https://docs.emqx.com/en/emqx/v5.8/guides/configuration/configuration.html)

CA ба төхөөрөмжийн файлыг Pi руу хуулна (`lab02/certs/` нь `.gitignore`-д байгаа):
```bash
# 💻
scp -i ~/.ssh/cnc302 certs/{ca.crt,pi3b-01.crt,pi3b-01.key} \
    cnc302@pi-team03.local:~/cnc302/lab02/certs/
```

Сертификаттай холбогдоно (🥧 Pi дээр):
```bash
cd ~/cnc302/lab02
export CLOUD_HOST=$(grep '^CLOUD_HOST=' ../edge/.env | cut -d= -f2)
mosquitto_pub -h $CLOUD_HOST -p 8883 -d \
  --cafile certs/ca.crt --cert certs/pi3b-01.crt --key certs/pi3b-01.key \
  -t 'cnc302/shutis/mhts/lab/pi3b-01/telemetry' -m '{"tls":true}'
# → Client … received CONNACK (0)
```

Сертификатгүй холбогдоно — **татгалзах ёстой**:
```bash
mosquitto_pub -h $CLOUD_HOST -p 8883 -d --cafile certs/ca.crt \
  -t 'cnc302/shutis/mhts/lab/pi3b-01/telemetry' -m '{"tls":false}'
# → OpenSSL Error[0]: … tlsv13 alert certificate required
# → Error: The connection was lost.
```

Өөрөө гарын үсэг зурсан (манай CA-гаар батлагдаагүй) сертификатаар оролдож үз — мөн татгалзах ёстой:
```bash
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=pi3b-01 \
  -keyout /tmp/rogue.key -out /tmp/rogue.crt
mosquitto_pub -h $CLOUD_HOST -p 8883 --cafile certs/ca.crt \
  --cert /tmp/rogue.crt --key /tmp/rogue.key -t test -m x
```

> Албан ёсны баримт: [mosquitto_pub(1)](https://mosquitto.org/man/mosquitto_pub-1.html) — `--cafile`, `--cert`, `--key`, `-d`. `--insecure` (хостын нэр шалгахгүй) -ийг бүү хэрэглэ: SAN зөв бол шаардлагагүй.

#### Хүснэгт 2.3 — mTLS-ийн үнэ

| Хэмжигдэхүүн | 1883 (TLS-гүй) | 8883 (mTLS) | Ялгаа |
|---|---|---|---|
| Холбогдох хугацаа (мс) | | | |
| p50 саатал, QoS 1 (мс) | | | |
| p99 саатал (мс) | | | |
| Pi-гийн CPU % нийтлэх үед | | | |

Хэмжих:
```bash
# 🥧 Pi дээр (~/cnc302/lab02)
python3 ../tools/qos_latency.py --host $CLOUD_HOST --port 1883 --path lan --count 200
python3 ../tools/qos_latency.py --host $CLOUD_HOST --port 8883 --path lan --count 200 \
        --tls --ca certs/ca.crt --cert certs/pi3b-01.crt --key certs/pi3b-01.key
```

> **Pi 3B-гийн онцлог — өөрсдөө шалга.** Armv8-ийн Cryptography Extension (AES/SHA-ийн техник хангамжийн заавар) нь Cortex-A53-д *сонголттой* хэсэг; BCM2837 түүнийг агуулдаг эсэхийг Raspberry Pi-гийн баримт тодорхой заагаагүй. Тиймээс таамаглах биш, хэмжинэ:
> ```bash
> grep -m1 Features /proc/cpuinfo      # aes, sha1, sha2, pmull байгаа эсэх
> openssl speed -evp aes-128-gcm        # Pi дээр ба компьютер дээр харьцуул
> ```
> Хэрэв `aes`/`sha2` алга бол TLS-ийн шифрлэлт бүхэлдээ програмаар хийгдэж, CPU-гийн зардал өндөр байна — ирмэгийн төхөөрөмж сонгохдоо анхаарах бодит хүчин зүйл.

---

### Алхам 4 — OTA: аз жаргалтай зам (35 мин) 💻🥧

Firmware дүрс байршуулна (жинхэнэ биш, санамсаргүй өгөгдөл — протокол л чухал):

```bash
# 💻 компьютер дээр
head -c 524288 /dev/urandom > /tmp/fw-1.2.0.bin      # 512 KiB
curl -s -X POST "localhost:8090/firmware?version=1.2.0" \
     -F "file=@/tmp/fw-1.2.0.bin" | jq
# → {"fw_id":"…","version":"1.2.0","size":524288,"chunks":128,"sha256":"…"}
```

🥧 Pi дээр OTA клиентийг ажиллуулна:
```bash
cd ~/cnc302/lab02
python3 ota_agent.py --host $CLOUD_HOST --device pi3b-01 --out out/fw --once
```

💻 Тараалт эхлүүлнэ:
```bash
FW=<дээрх fw_id>
curl -s -X POST localhost:8090/rollout -H 'content-type: application/json' \
  -d "{\"fw_id\":\"$FW\",\"canary_percent\":100,\"devices\":[\"pi3b-01\"]}" | jq
```

Pi дээрх лог `DOWNLOADING → … → UPDATED` дарааллыг харуулах ёстой.

> `offer` мессеж retained биш: агент **эхэлж** ажиллаж, захиалгаа хийсэн байх ёстой, дараа нь л тараалтыг эхлүүлнэ. Эс бөгөөс агент саналыг хэзээ ч авахгүй.

Хүснэгт 2.4-ийн гурван зам (агент бүрийг ажиллуулаад дээрх `rollout`-ыг дахин дуудна):
```bash
# 🥧 Pi → үүл шууд (LAN)
python3 ota_agent.py --host $CLOUD_HOST --device pi3b-01 --out out/fw --once
# 🥧 Pi → гүүрээр: Pi-гийн mosquitto руу холбогдоно (ota/# нь гүүрийн "in" сэдэвт бий)
python3 ota_agent.py --host localhost --device pi3b-01 --out out/fw --once
# 💻 (лавлагаа) loopback: компьютер дээр, EMQX руу шууд
python3 ota_agent.py --host localhost --device pi3b-01 --out /tmp/fw-loop --once
```

#### Хүснэгт 2.4 — OTA-гийн гүйцэтгэл (512 KiB, 128 хэсэг)

| Зам | Нийт хугацаа (сек) | KiB/сек | Хэсэг/сек | Тэмдэглэл |
|---|---|---|---|---|
| Pi → үүл шууд (LAN) | | | | |
| Pi → гүүрээр | | | | |
| (лавлагаа) loopback | | | | |

Файлын хэмжээг өөрчилж давт: 128 KiB, 512 KiB, 2 MiB.

| Хэмжээ | Хэсэг | Хугацаа (сек) | KiB/сек |
|---|---|---|---|
| 128 KiB | 32 | | |
| 512 KiB | 128 | | |
| 2 MiB | 512 | | |

> **Асуулт:** хурд нь хэмжээтэй шугаман өсөж байна уу? Үгүй бол хязгаарлагч нь юу вэ — 100 Mbit сүлжээ, microSD-гийн бичилт, эсвэл MQTT-ийн round-trip? (Санамж: 128 хэсэг × round-trip.)

---

### Алхам 5 — OTA: эвдрэлийн гурван хувилбар (40 мин) 🥧

Гурвуулангийн гаралтыг тайланд хадгална. Хувилбар бүрт 💻 компьютер дээр **шинэ** тараалт эхлүүлнэ. Rollback-ийг бодитоор харахын тулд өөр агуулгатай 2-р хувилбар (1.3.0) байршуулна — эс бөгөөс `current.bin` ба `previous.bin` ижил файл тул юу ч батлахгүй:

```bash
# 💻
head -c 131072 /dev/urandom > /tmp/fw-1.3.0.bin
FW2=$(curl -s -X POST "localhost:8090/firmware?version=1.3.0" \
      -F "file=@/tmp/fw-1.3.0.bin" | jq -r .fw_id)
offer() { curl -s -X POST localhost:8090/rollout -H 'content-type: application/json' \
  -d "{\"fw_id\":\"$FW2\",\"canary_percent\":100,\"devices\":[\"pi3b-01\"]}" | jq -c; }
# 🥧 агентыг ажиллуулсны ДАРАА 💻 дээр `offer` гэж дуудна
```

**А. Шалгалт унах (checksum failure)**
```bash
python3 ota_agent.py --host $CLOUD_HOST --device pi3b-01 --out out/fw --once --fail-verify
```
Хүлээгдэх: `DOWNLOADED → FAILED`. **Суулгахгүй.** `out/fw/version.txt` өөрчлөгдөөгүй (1.2.0) байх ёстой.

**Б. Суулгасны дараа ачаалагдахгүй (rollback)**
```bash
python3 ota_agent.py --host $CLOUD_HOST --device pi3b-01 --out out/fw --once --fail-apply
```
Хүлээгдэх: `VERIFIED → UPDATING → ROLLED_BACK`. `out/fw/current.bin` нь `previous.bin` (1.2.0)-тэй ижил болж, `version.txt` нь 1.2.0 хэвээр үлдсэнийг батал:
```bash
sha256sum out/fw/current.bin out/fw/previous.bin
cat out/fw/version.txt
```

**В. Сүлжээний алдагдал**
```bash
python3 ota_agent.py --host $CLOUD_HOST --device pi3b-01 --out out/fw --once \
        --drop-rate 0.2 --retry-after 1.0 --max-retries 8
```

#### Хүснэгт 2.5 — Эвдрэлийн хариу үйлдэл

| Хувилбар | Эцсийн төлөв | Хугацаа (сек) | Алдагдсан хэсэг | Дахин гуйсан тоо | Хуучин хувилбар хадгалагдсан уу |
|---|---|---|---|---|---|
| Хэвийн | UPDATED | | 0 | 0 | — |
| `--fail-verify` | | | | | |
| `--fail-apply` | | | | | |
| `--drop-rate 0.2` | | | | | |

> **Хүлээгдэх ажиглалт:** 20% алдагдалтай үед татах хугацаа **10–40 дахин** уртасна. Яагаад ийм их вэ? (Санамж: `--retry-after` нь тогтмол хүлээлт; алдагдал бүрд бүтэн завсарлага зарцуулагдана.)

---

### Алхам 6 — Canary тараалт ба буцаалт (35 мин) 💻

Виртуал флот дээр canary-г туршина.

```bash
# 20 виртуал төхөөрөмж бүртгэнэ
python3 provision.py bulk --count 20 --prefix ota --out out/ota.csv

# 20 OTA клиент зэрэг ажиллуулна (2 нь эвдэрсэн байхаар)
for i in $(seq -w 1 18); do
  python3 ota_agent.py --host localhost --device ota00$i --out out/f$i --once &
done
for i in 19 20; do
  python3 ota_agent.py --host localhost --device ota00$i --out out/f$i --once --fail-apply &
done
sleep 3

# Canary 20% (жагсаалтын ЭХНИЙ 4 төхөөрөмж). `devices`-ийг заавал өгнө —
# эс бөгөөс хүчингүй болоогүй БҮХ төхөөрөмж (dev*, b100*, b500* …) зорилт болно.
DEVS=$(seq -f '"ota%04g"' 1 20 | paste -sd, -)
RID=$(curl -s -X POST localhost:8090/rollout -H 'content-type: application/json' \
  -d "{\"fw_id\":\"$FW\",\"canary_percent\":20,\"devices\":[$DEVS]}" | jq -r .rollout_id)

sleep 10
curl -s localhost:8090/rollout/$RID | jq '.summary, .success_rate'

# Canary-гийн БҮХ төхөөрөмж UPDATED бол бусдад тараана (эс бөгөөс HTTP 409)
curl -s -X POST localhost:8090/rollout/$RID/promote | jq
```

#### Хүснэгт 2.6 — Canary тараалт

| Давалгаа | Төхөөрөмж | UPDATED | FAILED / ROLLED_BACK | Амжилтын % | Хугацаа |
|---|---|---|---|---|---|
| Canary (20%) | | | | | |
| Бүрэн (80%) | | | | | |
| **Нийт** | 20 | | | | |

Одоо **canary унасан** хувилбарыг туршина: агентуудыг дахин ажиллуулаад `devices` жагсаалтын эхэнд `"ota0019","ota0020"`-ийг тавьж canary-д оруул, дараа нь `promote` дууд. (Хүлээгдэх: HTTP 409, `rollout.state` = `halted`; дахин `promote` дуудсан ч 409.)

---

### Алхам 7 — Хүчингүй болгох (revocation) (25 мин) 💻

Хүчингүй болгохыг шалгахын тулд EMQX нэвтрэлт шаардах ёстой. Алхам 0-д үүсгэсэн authenticator-ыг **түр** идэвхжүүлнэ. Идэвхтэй үед нэр/нууц үггүй **бүх шинэ** холболт татгалзагдана (гүүр, `registry`, OTA агент). Одоо холбогдсон байгаа клиентүүд тасрахгүй — нэвтрэлтийг зөвхөн CONNECT үед шалгадаг.

```bash
# 💻 (Алхам 0-ийн EMQX_API_KEY / EMQX_API_SECRET export хийсэн терминал)
AUTHN=localhost:18083/api/v5/authentication/password_based%3Abuilt_in_database
authn() { curl -s -o /dev/null -w "authn enable=$1 → HTTP %{http_code}\n" \
  -u "$EMQX_API_KEY:$EMQX_API_SECRET" -X PUT "$AUTHN" -H 'content-type: application/json' \
  -d "{\"mechanism\":\"password_based\",\"backend\":\"built_in_database\",
       \"user_id_type\":\"username\",
       \"password_hash_algorithm\":{\"name\":\"sha256\",\"salt_position\":\"suffix\"},
       \"enable\":$1}"; }
authn true                                                   # → HTTP 204

PW=$(grep '^dev0001,' out/devices.csv | cut -d, -f3)
mosquitto_pub -h localhost -u dev0001 -P "$PW" -t 'cnc302/shutis/mhts/lab/dev0001/telemetry' -m '{"test":1}' \
  && echo "нэвтрэлт OK"
mosquitto_pub -h localhost -t 'cnc302/shutis/mhts/lab/dev0001/telemetry' -m x   # нэргүй → "bad user name or password"

# «Хулгайлагдсан» төхөөрөмж холбогдсон хэвээр байна (тусдаа терминал)
mosquitto_sub -h localhost -u dev0001 -P "$PW" -i dev0001-live -t 'cnc302/shutis/mhts/lab/dev0001/#' -v
```

Одоо хүчингүй болгоно:
```bash
python3 provision.py revoke --device-id dev0001
# ✓ dev0001 хүчингүй боллоо (EMQX хэрэглэгч: deleted)
#   Хөөсөн идэвхтэй холболт: ['dev0001-live']
python3 provision.py list --state revoked
mosquitto_pub -h localhost -u dev0001 -P "$PW" -t 'cnc302/shutis/mhts/lab/dev0001/telemetry' -m x
# → Connection error: Connection Refused: not authorised.
```

`registry` хүчингүй болгохдоо **гурван** зүйл хийнэ (`app.py` → `revoke()`): бүртгэлд `revoked` гэж тэмдэглэнэ → EMQX-ээс хэрэглэгчийг устгана (`DELETE /api/v5/authentication/{id}/users/{user_id}`) → тухайн username-тэй клиентүүдийг хайж (`GET /api/v5/clients?username=`) хөөнө (`DELETE /api/v5/clients/{clientid}`). **Хөөх алхамгүй бол яах вэ?** `dev0002`-оор `mosquitto_sub`-ийг (`-i dev0002-live`) дахин холбоод, хэрэглэгчийг зөвхөн EMQX-ээс устга:
```bash
curl -s -o /dev/null -w '%{http_code}\n' -u "$EMQX_API_KEY:$EMQX_API_SECRET" -X DELETE \
  "localhost:18083/api/v5/authentication/password_based%3Abuilt_in_database/users/dev0002"   # 204
curl -s -u "$EMQX_API_KEY:$EMQX_API_SECRET" "localhost:18083/api/v5/clients?username=dev0002" \
  | jq '[.data[].clientid]'          # → ["dev0002-live"] — холбогдсон хэвээр!
```
Нэвтрэлт устсан ч session амьд үлдэж, өгөгдөл илгээсээр байна. Дараа нь `python3 provision.py revoke --device-id dev0002` — одоо л тасарна.

Дуусаад authenticator-ыг **заавал** унтраана (гүүр, агент дахин холбогдох боломжтой болно):
```bash
authn false                                                  # → HTTP 204
```

> Албан ёсны баримт: [EMQX — Authentication (chain, ignore/deny)](https://docs.emqx.com/en/emqx/v5.8/guides/access-control/authn/authn.html) · [Manage user data via HTTP API](https://docs.emqx.com/en/emqx/v5.8/guides/access-control/authn/user_management.html) · [Dashboard — Clients (Kick Out)](https://docs.emqx.com/en/emqx/v5.8/guides/dashboard/connections.html). `DELETE /api/v5/clients/{clientid}` («Kick out client by client ID») нь EMQX-ийн Swagger баримтад (`http://localhost:18083/api-docs`) бий.

#### Хүснэгт 2.7 — Хүчингүй болгох

| Асуулт | Хариу |
|---|---|
| Шинэ холболт татгалзаж байна уу | |
| Одоо байгаа session тасарсан уу | |
| Хэдэн секундын дараа тасарсан | |
| X.509 бол CRL/OCSP хэрэгтэй юу | |

---

### Алхам 8 — Сонголтот: ThingsBoard-тай харьцуулах (25 мин) 💻

> Зөвхөн компьютерт ≥ 16 GB RAM байвал. ThingsBoard-ын албан ёсны заавар хөгжүүлэлт/PoC-д 1 цөм, **4 GB RAM**-ыг доод шаардлага гэж заасан.

```bash
cd ~/cnc302/stack
docker compose -f docker-compose.yml -f docker-compose.tb.yml \
  --profile core --profile tb up -d
# 2–3 минут хүлээнэ
docker stats --no-stream cnc302-thingsboard
```

http://localhost:8080 — анхдагч нэвтрэлт: **System Administrator** `sysadmin@thingsboard.org` / `sysadmin`. Системийн админ төхөөрөмж үүсгэдэггүй — түрээслэгч (tenant) удирддаг. Демо өгөгдөлтэй суусан бол `tenant@thingsboard.org` / `tenant`-аар нэвтэр; эс бөгөөс sysadmin-аар **Tenants → +** шинэ tenant ба tenant admin үүсгэ. Дараа нь tenant admin-аар **Entities → Devices → + Add device**.

> Албан ёсны баримт: [ThingsBoard — Installing using Docker](https://thingsboard.io/docs/installation/docker/)

#### Хүснэгт 2.8 — Өөрсдийн бүртгэл vs ThingsBoard

| Шалгуур | `registry` (бидний) | ThingsBoard |
|---|---|---|
| RAM (MiB) | | |
| Эхлэх хугацаа (сек) | | |
| Кодын мөрийн тоо | ~500 (`wc -l registry/app.py`) | (GitHub сангаас тооцоол) |
| Pi 3B дээр ажиллах уу | | |
| Rule engine, UI, олон түрээслэгч | ✗ | ✓ |
| Протокол ил харагдах уу | ✓ | ✗ |

Дуусаад **заавал** зогсооно (санах ой суллана):
```bash
docker compose -f docker-compose.yml -f docker-compose.tb.yml --profile tb stop thingsboard
```

---

### Алхам 9 — Git commit (10 мин)

```bash
cd ~/cnc302
git add lab02/ stack/ edge/
git commit -m "Лаб 2: бүртгэл, mTLS, OTA, canary тараалт"
git tag lab02-done && git push && git push --tags

# Нууц файл ороогүй эсэхийг ЗААВАЛ шалга
git ls-files | grep -E '\.crt$|\.key$|devices\.csv|\.env$'   # хоосон байх ЁСТОЙ
```

---

## 5. Хяналтын асуултууд

1. Хүснэгт 2.1-д bulk бүртгэл шугаман өсөв үү? Хэрэв 100 000 төхөөрөмж бүртгэх бол одоогийн хэрэгжүүлэлт хэр хугацаа шаардах вэ? Хэрхэн хурдасгах вэ (хоёр арга)?

2. JIT бүртгэлийн эмзэг байдлыг **X.509-ээр** хэрхэн хаах вэ? Төхөөрөмж дээр хувийн түлхүүр яаж аюулгүй хадгалагдах вэ (Pi 3B-д TPM/Secure Element байхгүй — энэ юу гэсэн үг вэ)?

3. Хүснэгт 2.3-д mTLS-ийн саатлын нэмэгдэл хэдэн хувь байв? Таны Pi-гийн `/proc/cpuinfo`-д `aes`/`sha2` байсан уу, `openssl speed` Pi ба компьютер дээр хэд дахин ялгаатай гарав? 1 000 төхөөрөмжтэй флотод энэ ямар үр дагавартай вэ?

4. Хүснэгт 2.4-т OTA-гийн хурд файлын хэмжээтэй шугаман өсөв үү? Хэрэв хязгаарлагч нь round-trip бол `chunk_size`-ыг 4 KiB-аас 64 KiB болговол юу өөрчлөгдөх вэ? Ямар эрсдэл нэмэгдэх вэ?

5. `--fail-apply` тохиолдолд манай агент `previous.bin`-ээс сэргээв. Жинхэнэ төхөөрөмжид (жишээ нь ESP32) энэ хэрхэн хийгддэг вэ? A/B хуваалт хэдэн % илүү флеш шаарддаг вэ?

6. Canary 20% нь 5 000 төхөөрөмжийн флотод 1 000 төхөөрөмж болно. Энэ хэт олон уу? Canary-гийн хэмжээг юугаар тодорхойлох вэ?

7. Алхам 7-д зөвхөн хэрэглэгчийг устгахад **одоо байгаа** холболт тасраагүй. Энэ ямар халдлагын боломж олгох вэ? `registry` хөөх алхмыг нэмсэн ч ямар цоорхой үлдэх вэ (жишээ нь X.509-ээр холбогдсон төхөөрөмж)? MQTT 5.0-ийн ямар боломж (`Session Expiry Interval`, сервер талаас илгээх `DISCONNECT`) үүнд тусалж болох вэ?

---

## 6. Хүлээлгэн өгөх зүйл

| # | Зүйл | Байрлал |
|---|---|---|
| 1 | Тайлан (Хүснэгт 2.1–2.7, сонголтоор 2.8) | `lab02/report.md` → PDF |
| 2 | OTA-гийн дөрвөн хувилбарын лог | `lab02/out/*.log` |
| 3 | Багийн таних тэмдгийн стратеги (½ хуудас) | тайлангийн хавсралт |
| 4 | Git tag | `lab02-done` |

⛔ Сертификат, түлхүүр, `devices.csv` **Git-д орохгүй**.

---

## 7. Үнэлгээний шалгуур (10 оноо)

| Шалгуур | Оноо |
|---|---|
| Bulk + JIT + mTLS ажиллаж байна (амьд үзүүлнэ) | 3 |
| OTA-гийн 4 хувилбар бүгд хэмжигдсэн, Хүснэгт 2.4–2.5 бүрэн | 3 |
| Canary + rollback ажилласан, тоогоор баримтжуулсан | 2 |
| Таних тэмдгийн стратеги үндэслэлтэй | 1 |
| Git цэвэр, нууц файл ороогүй | 1 |

---

## 8. Түгээмэл алдаа

| Шинж | Шалтгаан | Шийдэл |
|---|---|---|
| `бүртгэлийн үйлчилгээнд хүрэхгүй` | `registry` асаагүй | 💻 `cd stack && make up` |
| OTA-д санал ирэхгүй | сэдвийн угтвар / SITE зөрсөн | troubleshooting §2 |
| mTLS: `TLS error` зөв сертификаттай ч | цаг синхрончлогдоогүй | 🥧 `timedatectl status` |
| `openssl verify` → error 10 | сертификат хугацаа дууссан | `make_certs.sh device <нэр>` дахин |
| OTA хэт удаан (>5 мин) | throttling эсвэл Wi-Fi | `vcgencmd get_throttled`, кабель |
| OTA-д санал ирэхгүй, агент 180 сек хүлээгээд гарна | тараалтыг агентаас ӨМНӨ эхлүүлсэн (offer retained биш) | агентыг эхлүүлээд `rollout`-ыг дахин дууд |
| mTLS: `host name verification failed` | серверийн сертификатын SAN-д `CLOUD_HOST` алга | `CLOUD_HOST=<IP> ./make_certs.sh server`, EMQX-д дахин хуулна |
| mTLS: `TLS error` зөв сертификаттай ч | цаг синхрончлогдоогүй | 🥧 `timedatectl status` |
| Сертификатгүй клиент 8883-т холбогдчихлоо | `verify_peer` / `fail_if_no_peer_cert` тохируулаагүй | `curl …/api/v5/listeners/ssl:default` → `ssl_options` шалга |
| `devices.csv`-д `emqx = error 404` | authenticator үүсгээгүй | Алхам 0-ийн 3 |
| `devices.csv`-д `emqx = skipped` | `EMQX_API_KEY` хоосон | Алхам 0-ийн 1–2 |
| Алхам 7-ийн дараа гүүр/агент холбогдохгүй | authenticator идэвхтэй хэвээр | `authn false` |
| `openssl verify` → error 10 | сертификат хугацаа дууссан | `make_certs.sh device <нэр>` дахин |
| OTA хэт удаан (>5 мин) | throttling эсвэл Wi-Fi | `vcgencmd get_throttled`, кабель |
| `promote` → HTTP 409 | canary-д алдаа гарсан эсвэл дуусаагүй | зөв ажиллаж байна — `detail`, лог шалга |

---

## 9. Эх сурвалж

| # | Эх сурвалж | Юуг баталгаажуулсан | Хандсан |
|---|---|---|---|
| 1 | [EMQX 5.8 — REST API](https://docs.emqx.com/en/emqx/v5.8/guides/api.html) | суурь зам `/api/v5`, API key/secret-ээр HTTP Basic, самбарын нэвтрэлт REST-д ажиллахгүй, 201/204/404/409 кодууд | 2026-09 |
| 2 | [EMQX 5.8 — API Keys](https://docs.emqx.com/en/emqx/v5.8/guides/api-keys.html) | System → API Key → Create; secret нэг л удаа харагдана | 2026-09 |
| 3 | [EMQX 5.8 — Authentication](https://docs.emqx.com/en/emqx/v5.8/guides/access-control/authn/authn.html) | анхдагчаар нээлттэй; сүүлийн authenticator-т олдоогүй бол татгалзана; ID `password_based:built_in_database`, `:` → `%3A` | 2026-09 |
| 4 | [EMQX 5.8 — Built-in Database](https://docs.emqx.com/en/emqx/v5.8/guides/access-control/authn/mnesia.html) | `mechanism`, `backend`, `user_id_type`, `password_hash_algorithm` | 2026-09 |
| 5 | [EMQX 5.8 — Manage user data via HTTP API](https://docs.emqx.com/en/emqx/v5.8/guides/access-control/authn/user_management.html) | `/api/v5/authentication/{id}/users` | 2026-09 |
| 6 | [EMQX 5.8 — Enable SSL/TLS Connection](https://docs.emqx.com/en/emqx/v5.8/guides/network/emqx-mqtt-tls.html) | 8883 анхдагчаар нэг талын; mTLS-д `verify = verify_peer`, `fail_if_no_peer_cert = true` | 2026-09 |
| 7 | [EMQX 5.8 — Configuration](https://docs.emqx.com/en/emqx/v5.8/guides/configuration/configuration.html) | орчны хувьсагч: `EMQX_` угтвар, `.` → `__` | 2026-09 |
| 8 | [EMQX 5.8 — CRL Check](https://docs.emqx.com/en/emqx/v5.8/guides/network/crl.html) | CRL-ийг сертификатын CRL Distribution Point-оос татна; зөвхөн `ssl` сонсогч | 2026-09 |
| 9 | [EMQX 5.8 — Dashboard: Clients](https://docs.emqx.com/en/emqx/v5.8/guides/dashboard/connections.html) | Kick Out | 2026-09 |
| 10 | [mosquitto_pub(1)](https://mosquitto.org/man/mosquitto_pub-1.html) | `--cafile`, `--cert`, `--key`, `-d`, `--insecure` | 2026-09 |
| 11 | [openssl-req(1)](https://docs.openssl.org/3.0/man1/openssl-req/) · [openssl-x509(1)](https://docs.openssl.org/3.0/man1/openssl-x509/) · [openssl-verify(1)](https://docs.openssl.org/3.0/man1/openssl-verify/) | `-subj`, `-x509`, `-req -CA -CAkey -CAcreateserial -extfile`, `-ext`, `-CAfile` | 2026-09 |
| 12 | [x509v3_config(5)](https://docs.openssl.org/3.0/man5/x509v3_config/) | `subjectAltName`, `extendedKeyUsage = serverAuth / clientAuth` | 2026-09 |
| 13 | [Eclipse Paho Python — Migrations (2.0)](https://eclipse.dev/paho/files/paho.mqtt.python/html/migrations.html) · [Client](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html) | `CallbackAPIVersion.VERSION2`, `on_connect(client, userdata, flags, reason_code, properties)`, `on_disconnect(…, flags, reason_code, properties)`, `tls_set`, `username_pw_set` | 2026-09 |
| 14 | [FastAPI — Request Files](https://fastapi.tiangolo.com/tutorial/request-files/) · [Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) | `UploadFile` нь `python-multipart` шаардана; `lifespan` | 2026-09 |
| 15 | [Raspberry Pi — BCM2837](https://www.raspberrypi.com/documentation/computers/processors.html#bcm2837) (эх: [bcm2837.adoc](https://github.com/raspberrypi/documentation/blob/master/documentation/asciidoc/computers/processors/bcm2837.adoc)) | Cortex-A53 (Armv8); крипто өргөтгөлийн тухай дурдаагүй | 2026-09 |
| 16 | [ThingsBoard — Installing using Docker](https://thingsboard.io/docs/installation/docker/) | `sysadmin@thingsboard.org` / `sysadmin`; `tenant@…` зөвхөн демо өгөгдөлтэй; Dev/PoC 4 GB RAM | 2026-09 |
