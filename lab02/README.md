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

Худалдааны платформууд (ThingsBoard, AWS IoT, Azure IoT Hub) эдгээрийг **хар хайрцаг** болгож нуудаг. Энэ лабораторид та `lab02/registry/app.py` (≈400 мөр) ба `lab02/ota_agent.py` (≈300 мөр) хоёрыг **уншиж, ажиллуулж, эвдэж** протоколыг ил харна.

> **Яагаад ThingsBoard биш вэ:** ThingsBoard-ын JVM 1.5–2.5 GB шаарддаг. Pi 3B-д 925 MiB. Гэхдээ илүү чухал шалтгаан бий — та энэ хичээлээр *платформ ашиглагч* биш *платформ зохиогч* болох ёстой. Лабораторийн эцэст сонголтот харьцуулалт хийнэ (§4, Алхам 7).

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

> Хугацаа **шугаман** өсөж байна уу? Үгүй бол хаана бөглөрч байна вэ? (Санамж: SQLite нэг бичилт бүрд диск рүү fsync хийдэг.)

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

Өөрсдийн CA үүсгэж, төхөөрөмжид сертификат олгоно.

```bash
# 💻 компьютер дээр
cd ~/cnc302/lab02
./make_certs.sh init                       # CA үүсгэнэ
./make_certs.sh device pi3b-01
./make_certs.sh device dev0001
./make_certs.sh list

# Гинжин хэлхээг батлах
openssl verify -CAfile certs/ca.crt certs/pi3b-01.crt    # → OK
openssl x509 -in certs/pi3b-01.crt -noout -subject -dates
```

EMQX-д mTLS сонсогчийг асаана:
```bash
cd ~/cnc302/stack
cp ../lab02/certs/{ca.crt,server.crt,server.key} emqx/certs/
sed -i 's/^EMQX_TLS_ENABLE=.*/EMQX_TLS_ENABLE=true/' .env
docker compose --profile core up -d emqx
docker compose logs emqx | grep -i ssl | tail -5
```

Сертификаттай холбогдож үзнэ (🥧 Pi дээр — CA ба төхөөрөмжийн файлыг хуулж авна):
```bash
mosquitto_pub -h $CLOUD_HOST -p 8883 \
  --cafile ca.crt --cert pi3b-01.crt --key pi3b-01.key \
  -t 'cnc302/shutis/mhts/lab/pi3b-01/telemetry' -m '{"tls":true}'
```

Сертификатгүй холбогдож үзнэ — **татгалзах ёстой**:
```bash
mosquitto_pub -h $CLOUD_HOST -p 8883 --cafile ca.crt \
  -t 'cnc302/shutis/mhts/lab/pi3b-01/telemetry' -m '{"tls":false}'
# → Error: A TLS error occurred
```

#### Хүснэгт 2.3 — mTLS-ийн үнэ

| Хэмжигдэхүүн | 1883 (TLS-гүй) | 8883 (mTLS) | Ялгаа |
|---|---|---|---|
| Холбогдох хугацаа (мс) | | | |
| p50 саатал, QoS 1 (мс) | | | |
| p99 саатал (мс) | | | |
| Pi-гийн CPU % нийтлэх үед | | | |

Хэмжих:
```bash
# 🥧 Pi дээр
python3 ../tools/qos_latency.py --host $CLOUD_HOST --port 1883 --path lan --count 200
python3 ../tools/qos_latency.py --host $CLOUD_HOST --port 8883 --path lan --count 200 \
        --tls --ca ca.crt --cert pi3b-01.crt --key pi3b-01.key
```

> **Pi 3B-гийн онцлог:** Cortex-A53 нь ARMv8 крипто өргөтгөлгүй (AES, SHA хурдасгуургүй). Тиймээс TLS-ийн зардал Pi 5 эсвэл компьютер дээрхээс **мэдэгдэхүйц** өндөр. Энэ бол ирмэгийн төхөөрөмж сонгохдоо анхаарах бодит хүчин зүйл.

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

> **Асуулт:** хурд нь хэмжээтэй шугаман өсөж байна уу? Үгүй бол хязгаарлагч нь юу вэ — 100 Mbit сүлжээ, microSD-гийн бичилт, эсвэл MQTT-ийн round-trip? (Санамз: 128 хэсэг × round-trip.)

---

### Алхам 5 — OTA: эвдрэлийн гурван хувилбар (40 мин) 🥧

Гурвуулангийн гаралтыг тайланд хадгална.

**А. Шалгалт унах (checksum failure)**
```bash
python3 ota_agent.py --host $CLOUD_HOST --device pi3b-01 --out out/fw --once --fail-verify
```
Хүлээгдэх: `DOWNLOADED → FAILED`. **Суулгахгүй.** `out/fw/version.txt` өөрчлөгдөөгүй байх ёстой.

**Б. Суулгасны дараа ачаалагдахгүй (rollback)**
```bash
python3 ota_agent.py --host $CLOUD_HOST --device pi3b-01 --out out/fw --once --fail-apply
```
Хүлээгдэх: `VERIFIED → UPDATING → ROLLED_BACK`. `out/fw/current.bin` нь `previous.bin`-тэй ижил болсон эсэхийг батал:
```bash
sha256sum out/fw/current.bin out/fw/previous.bin
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
  python3 ota_agent.py --host $CLOUD_HOST --device ota00$i --out out/f$i --once &
done
for i in 19 20; do
  python3 ota_agent.py --host $CLOUD_HOST --device ota00$i --out out/f$i --once --fail-apply &
done

# Canary 20% (4 төхөөрөмж)
curl -s -X POST localhost:8090/rollout -H 'content-type: application/json' \
  -d "{\"fw_id\":\"$FW\",\"canary_percent\":20}" | jq
RID=<буцаасан rollout_id>

sleep 30
curl -s localhost:8090/rollout/$RID | jq '.summary, .success_rate'

# Canary амжилттай бол бусдад тараана
curl -s -X POST localhost:8090/rollout/$RID/promote | jq
```

#### Хүснэгт 2.6 — Canary тараалт

| Давалгаа | Төхөөрөмж | UPDATED | FAILED / ROLLED_BACK | Амжилтын % | Хугацаа |
|---|---|---|---|---|---|
| Canary (20%) | | | | | |
| Бүрэн (80%) | | | | | |
| **Нийт** | 20 | | | | |

Одоо **canary унасан** хувилбарыг туршина: `--fail-apply`-тай төхөөрөмжийг canary давалгаанд оруулж, `promote` дуудвал юу болох вэ? (Хүлээгдэх: HTTP 409, тараалт зогсоно.)

---

### Алхам 7 — Хүчингүй болгох (revocation) (20 мин) 💻

```bash
python3 provision.py revoke --device-id dev0001
python3 provision.py list --state revoked
```

Хүчингүй болсон төхөөрөмж дахин холбогдож чадах уу? Туршиж үз:
```bash
mosquitto_pub -h localhost -p 1883 -u dev0001 -P '<devices.csv-ийн нууц үг>' \
  -t 'cnc302/shutis/mhts/lab/dev0001/telemetry' -m '{"test":1}'
```

**Гол ажиглалт:** аль хэдийн **холбогдсон** session яах вэ? EMQX самбар → Clients → тухайн клиентийг олж, гараар таслах хэрэгтэй. Энэ бол бодит системийн ноцтой цоорхой — хүчингүй болгосон боловч холбогдсон хэвээр байгаа төхөөрөмж цагийн турш өгөгдөл илгээж чадна.

#### Хүснэгт 2.7 — Хүчингүй болгох

| Асуулт | Хариу |
|---|---|
| Шинэ холболт татгалзаж байна уу | |
| Одоо байгаа session тасарсан уу | |
| Хэдэн секундын дараа тасарсан | |
| X.509 бол CRL/OCSP хэрэгтэй юу | |

---

### Алхам 8 — Сонголтот: ThingsBoard-тай харьцуулах (25 мин) 💻

> Зөвхөн компьютерт ≥ 16 GB RAM байвал.

```bash
cd ~/cnc302/stack
docker compose -f docker-compose.yml -f docker-compose.tb.yml \
  --profile core --profile tb up -d
# 2–3 минут хүлээнэ
docker stats --no-stream cnc302-thingsboard
```

http://localhost:8080 (sysadmin@thingsboard.org / sysadmin) → Devices → Add device.

#### Хүснэгт 2.8 — Өөрсдийн бүртгэл vs ThingsBoard

| Шалгуур | `registry` (бидний) | ThingsBoard |
|---|---|---|
| RAM (MiB) | | |
| Эхлэх хугацаа (сек) | | |
| Кодын мөрийн тоо | ~400 | ~1 000 000+ |
| Pi 3B дээр ажиллах уу | | |
| Rule engine, UI, олон түрээслэгч | ✗ | ✓ |
| Протокол ил харагдах уу | ✓ | ✗ |

Дуусаад **заавал** зогсооно (санах ой суллана):
```bash
docker compose --profile tb stop thingsboard
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

3. Хүснэгт 2.3-д mTLS-ийн саатлын нэмэгдэл хэдэн хувь байв? Cortex-A53-д крипто хурдасгуур байхгүйг харгалзан, 1 000 төхөөрөмжтэй флотод энэ ямар үр дагавартай вэ?

4. Хүснэгт 2.4-т OTA-гийн хурд файлын хэмжээтэй шугаман өсөв үү? Хэрэв хязгаарлагч нь round-trip бол `chunk_size`-ыг 4 KiB-аас 64 KiB болговол юу өөрчлөгдөх вэ? Ямар эрсдэл нэмэгдэх вэ?

5. `--fail-apply` тохиолдолд манай агент `previous.bin`-ээс сэргээв. Жинхэнэ төхөөрөмжид (жишээ нь ESP32) энэ хэрхэн хийгддэг вэ? A/B хуваалт хэдэн % илүү флеш шаарддаг вэ?

6. Canary 20% нь 5 000 төхөөрөмжийн флотод 1 000 төхөөрөмж болно. Энэ хэт олон уу? Canary-гийн хэмжээг юугаар тодорхойлох вэ?

7. Хүчингүй болгосон төхөөрөмжийн **одоо байгаа** холболт тасрахгүй байв. Энэ ямар халдлагын боломж олгох вэ? MQTT 5.0-ийн ямар боломж (`Session Expiry Interval`, `Server Disconnect`) үүнд тусалж болох вэ?

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
| `promote` → HTTP 409 | canary-д алдаа гарсан | зөв ажиллаж байна — лог шалга |
