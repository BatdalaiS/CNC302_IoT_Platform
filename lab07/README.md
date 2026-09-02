# Лаб 7 — Хэрэглээний давхарга ба Zero Trust

| | |
|---|---|
| **7 хоног** | XIV |
| **Хугацаа** | 4 цаг |
| **Суралцахуйн үр дүн** | ҮД3 (үнэлэх), ҮД4 (аюулгүй зохиох), ҮД6 |
| **Үнэлгээ** | Бичгийн тайлан, 10 оноо |
| **Гол хэмжилт** | REST vs GraphQL, аюулгүй байдлын 9 шалгалт (засварын өмнө/дараа) |

---

## 1. Зорилго

Платформын дээр **хэрэглэгчийн давхаргыг** барьж, дараа нь түүнийг **эвдэхийг оролдоно**.

1. **Барих** — REST ба GraphQL-ийн ялгааг зохион бүтээх замаар ойлгох, Dex-ээр OIDC нэвтрэлт, RBAC үүрэг, бодит хугацааны шинэчлэл
2. **Эвдэх** — `security_tests.py`-г ажиллуулж эмзэг байдлыг олох, гараар батлах, **засах**, дахин ажиллуулж засварыг нотлох

> **Чухал:** `lab07/graphql-api/main.py` дотор **ЯГ ХОЁР санаатай эмзэг байдал** бий. Тэдгээрийг олж засах нь энэ лабораторийн гол ажил. Лабораторийн эцэст `security_tests.py` нь "Санаатай эмзэг байдал илрээгүй" гэж хэвлэх ёстой.

**💻 Энэ лаборатори бүхэлдээ үүлний давхаргад.** GraphQL API (:8000), Dex (:5556), бүртгэл (:8090), InfluxDB (:8181) — бүгд зөөврийн компьютер дээр. 🥧 Pi 3B нь зөвхөн ирмэгийн үүргээ гүйцэтгэнэ (mosquitto + агент). Pi дээр энэ лабораторид ажиллуулах комманд **байхгүй** — гэхдээ агент нь ажиллаж байх ёстой, эс бөгөөс InfluxDB-д унших өгөгдөл байхгүй.

---

## 2. Урьдчилсан нөхцөл

- Лаб 1–6 дууссан, `lab06-done` tag тавигдсан
- Бие даалт XIV: OAuth2 / OIDC-ийн authorization code урсгалыг уншсан

```bash
# 💻 үүлний давхаргыг app профайлтай асаана
cd ~/cnc302/stack && docker compose --profile core --profile pipeline --profile app up -d --build
make health                                          # бүх мөр 200
curl -s localhost:8000/health | jq                   # {"status":"ok","checks":{...200}}
curl -s localhost:5556/dex/.well-known/openid-configuration | jq .issuer

# 🥧 Pi дээр агент ажиллаж, өгөгдөл урсаж байх ёстой
cd ~/cnc302/edge && make up && make link             # bridge/state 1
```

Бүртгэлд төхөөрөмж байхгүй бол Лаб 2-ын bulk бүртгэлийг 💻 дээр дахин ажиллуул:
`python3 lab02/provision.py bulk --count 50 --prefix dev --out lab02/out/devices.csv`

---

## 3. Онолын сануулга

### REST-ийн 1+N асуудал, GraphQL-ийн шинэ эрсдэл

50 төхөөрөмж бүрийн сүүлийн 20 хэмжилтийг авахад REST-д **51 хүсэлт** хэрэгтэй (1 жагсаалт + 50 хэмжилт). GraphQL-д **1 хүсэлт**. IoT-д энэ нь жижиг зүйл биш: гар утасны апп сул сүлжээгээр 51 удаа тойрч гүйхэд хэдэн секунд алдана.

Гэхдээ клиент асуулгын **хэлбэрийг өөрөө** тодорхойлдог тул нэг хүсэлтээр серверийг ачаалж болно (гүн үүрлэсэн эсвэл олон давхар нэрлэсэн `alias` асуулга). REST-д ийм зүйл байхгүй — төгсгөлийн цэг бүр тогтмол өртөгтэй. Мөн `__schema` introspection нь довтолгооны газрын зургийг халдагчид үнэгүй өгнө.

### Танилт (authentication) ≠ Эрх (authorization)

Танилт: *чи хэн бэ?* → OIDC токен (Dex) → `decode_token()`.
Эрх: *чи юу хийж болох вэ?* → RBAC үүрэг → `Principal.require()`.

Хамгийн түгээмэл эмзэг байдал бол эхнийхийг хийгээд хоёр дахийг мартах, эсвэл **токеныг шалгалгүй итгэх**. Манай `main.py` яг сүүлийнхийг хийж байна.

### Хоёр эх сурвалж, нэг схем; Zero Trust

```
GraphQL :8000 ──┬──► registry :8090   төхөөрөмж, firmware, OTA (Лаб 2)
                └──► influxdb :8181   цаг цуваа (SQL, /api/v3/query_sql)
```

**ThingsBoard энд байхгүй.** Лаб 2-т бид бүртгэлээ өөрсдөө бичсэн тул түүн дээр GraphQL давхарга барихад юу ч нуугдахгүй.

**Zero Trust:** "дотоод сүлжээ тул аюулгүй" гэсэн таамаг **байхгүй**. Хүсэлт бүрийг шалгана — эх сурвалж хаанаас ирсэн нь хамаагүй. InfluxDB-г `--without-auth` горимд ажиллуулж байгаа нь тэр зарчмыг илт зөрчсөн жишээ (Алхам 8).

---

## 4. Алхмууд

### Алхам 1 — Бэлтгэл ба схемийг судлах (15 мин) 💻

Хөтчөөр `http://localhost:8000/graphql` нээж GraphiQL-ийг үзнэ. Токенгүйгээр зөвхөн `{ whoami }` ажиллана. `{ devices(limit: 5) { id name } }` бичвэл **алдаа** гарна: `'device:read' эрх байхгүй. Таны үүрэг: []`. Энэ бол зөв зан төлөв — Zero Trust-ын анхдагч: **токенгүй хүсэлт нэг ч үүрэггүй**. Тиймээс эхлээд токен авах хэрэгтэй → Алхам 2.

Схемийг GraphiQL-ийн Docs самбараас судал: `devices`, `device`, `firmware`, `anomalies`, `deviceStats` (хараахан байхгүй), `sendCommand`.

---

### Алхам 2 — OIDC токен ба үүргийн эх сурвалж (35 мин) 💻

**2.1 Токен авах.** Dex-д гурван статик хэрэглэгч бий: `viewer@`, `operator@`, `admin@cnc302.mn`, бүгд нууц үг `cnc302`. Энэ туслах функцийг лабораторийн турш ашиглана:

```bash
tok() { curl -s -X POST http://localhost:5556/dex/token -d grant_type=password \
  -d scope='openid email profile groups' -d client_id=cnc302 \
  -d client_secret=cnc302-lab-secret -d username="$1@cnc302.mn" -d password=cnc302 \
  | jq -r .id_token; }
TOKEN=$(tok admin) && echo "${TOKEN:0:40}…"
```

> `password` grant татгалзвал `stack/dex/config.yaml`-д `oauth2.passwordConnector: local` байгаа эсэхийг шалга, эсвэл authorization code урсгал руу шилж. Аль нь болсныг тайланд бич — OAuth2-ын урсгал бүр өөр аюулгүй байдлын шинжтэй.

**2.2 Токеныг API-д ашиглах. 2.3 Гурван хэрэглэгчээр давтах:**

```bash
for U in viewer operator admin; do
  printf '%-9s ' "$U"
  curl -s -X POST localhost:8000/graphql -H "Authorization: Bearer $(tok $U)" \
    -H 'Content-Type: application/json' -d '{"query":"{ whoami }"}' | jq -r .data.whoami
done
```

#### Хүснэгт 7.1 — Токеноос үүрэг хүртэл

| Хэрэглэгч | `id_token`-ы `groups` талбар байна уу | `whoami`-гийн `roles=` | `perms=` тоо |
|---|---|---|---|
| viewer@cnc302.mn | | | |
| operator@cnc302.mn | | | |
| admin@cnc302.mn | | | |

Токеныг задлан үзэх: `echo "$TOKEN" | cut -d. -f2 | base64 -d 2>/dev/null | jq`

**Ажиглалт:** Dex-ийн статик хэрэглэгчид `groups` талбар **агуулдаггүй**. `decode_token` нь `groups` олдохгүй бол `["viewer"]`-д унана — тиймээс **гурвуулаа viewer** болно. **2.4:** хоёр шийдлийг харьцуулж, нэгийг нь хэрэгжүүл.

#### Хүснэгт 7.2 — Үүргийн эх сурвалжийн сонголт

| | (а) Dex-д LDAP/GitHub холбогч | (б) API дээр имэйлээс үүрэг зурвасжуулах |
|---|---|---|
| Хэрэгжүүлэх хугацаа (мин) | | |
| Үүргийг хаана удирдах вэ | | |
| Токен хуурамч бол ажиллах уу | | |
| Үйлдвэрлэлд тохирох уу | | |
| **Бидний сонголт ба шалтгаан** | | |

Лабораторийн цагт (б)-г хэрэгжүүлэх нь бодитой: `decode_token`-д `claims.get("email")`-ээс `admin@` → `admin`, `operator@` → `operator` зурвасжуулна. Гэхдээ тайландаа **(а) яагаад илүү зөв болохыг** заавал бич.

---

### Алхам 3 — REST ба GraphQL-ийн харьцуулалт (45 мин) 💻

**3.1 GraphQL — нэг хүсэлт:**

```bash
time curl -s -X POST localhost:8000/graphql -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -o /tmp/gql5.json \
  -d '{"query":"{ devices(limit:5){ name state readings(limit:10){ time temperature vibrationRms } } }"}'
wc -c /tmp/gql5.json
```

**3.2 REST — 1 + N хүсэлт.** Эхлээд жагсаалт (`/rest/devices` нь ЗӨВХӨН жагсаалт буцаана), дараа нь төхөөрөмж тус бүрийн хэмжилт:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  'localhost:8000/rest/devices?limit=5' | jq -r '.devices[].name' > /tmp/devs.txt
time (while read d; do
  curl -s -X POST localhost:8181/api/v3/query_sql -H 'Content-Type: application/json' \
    -d "{\"db\":\"cnc302\",\"q\":\"SELECT time, temperature, vibration_rms FROM telemetry WHERE device='$d' ORDER BY time DESC LIMIT 10\",\"format\":\"json\"}"
done < /tmp/devs.txt) > /tmp/rest5.json
wc -l /tmp/devs.txt && wc -c /tmp/rest5.json
```

**3.3 50 төхөөрөмж дээр давт** (`limit:5` → `limit:50`). Ялгаа шугаман өсөв үү?

#### Хүснэгт 7.3 — REST ба GraphQL

| Хэмжилт | REST | GraphQL |
|---|---|---|
| 5 төхөөрөмж: хүсэлтийн тоо | | 1 |
| 5 төхөөрөмж: нийт хугацаа (мс) | | |
| 50 төхөөрөмж: хүсэлтийн тоо | | 1 |
| 50 төхөөрөмж: нийт хугацаа (мс) | | |
| 50 төхөөрөмж: хариуны байт | | |
| Илүүдэл өгөгдөл (over-fetching) байна уу | | |

> **Санамз:** REST-ийн хугацаа нь `localhost` дээр хамгийн таатай нөхцөлд хэмжигдэж байна. Сүлжээний саатал (RTT) 200 мс байсан бол 51 хүсэлт **дор хаяж 10 секунд** болно. Хяналтын асуулт 1-д үүнийг тоогоор гарга.

---

### Алхам 4 — `deviceStats` ба нэгтгэлийн байрлал (30 мин) 💻

`main.py` дотор `# TODO(оюутан)` гэсэн тэмдэглэгээ бий. Дараах талбарыг нэмнэ:

```graphql
{ deviceStats(device: "dev0001", hours: 24) { avg min max samples } }
```

**Дүрэм:** нэгтгэлийг **InfluxDB-д хийлгэнэ** (SQL-ийн `avg/min/max/count`), Python дээр биш:

```sql
SELECT avg(temperature) AS avg, min(temperature) AS min, max(temperature) AS max,
       count(temperature) AS samples
FROM telemetry WHERE device = '<...>' AND time > now() - INTERVAL '24 hours'
```

Дараа нь дахин барина: `docker compose --profile app up -d --build graphql-api`

**Хоёр хувилбарыг хэмж:** (а) SQL-д нэгтгэх, (б) бүх мөрийг татаад Python дээр нэгтгэх.

#### Хүснэгт 7.4 — Нэгтгэлийг хаана хийх вэ

| | InfluxDB дээр (SQL) | Python дээр (API) |
|---|---|---|
| Хариу ирэх хугацаа (мс), 24 цаг | | |
| InfluxDB-ээс татсан мөрийн тоо | | |
| Хариуны байт | | |
| 30 хоногийн өгөгдөл дээр (мс) | | |

**Дүгнэлт:** нэгтгэлийг өгөгдөлд ойр хийх зарчим яагаад чухал вэ: ______________

---

### Алхам 5 — Бодит хугацааны шинэчлэл: polling ба WebSocket (25 мин) 💻

**5.1 Одоогийн байдал — polling.** 1 секунд тутам асуух:

```bash
timeout 60 bash -c 'while true; do
  curl -s -o /dev/null -w "%{size_download} " -X POST localhost:8000/graphql \
    -H "Authorization: Bearer '"$TOKEN"'" -H "Content-Type: application/json" \
    -d "{\"query\":\"{ devices(limit:5){ name } }\"}"; sleep 1
done' | tr ' ' '\n' | awk '{s+=$1; n++} END {print n " хүсэлт, " s " байт"}'
```

**5.2 ОЮУТНЫ ДААЛГАВАР — WebSocket.** `main.py` дотор одоо WebSocket **байхгүй**. Хоёр замын аль нэгийг сонгож нэмнэ:

- (а) Strawberry-гийн `@strawberry.subscription` + `GraphQLRouter`-ын `graphql-ws` протокол
- (б) FastAPI-гийн `@app.websocket("/ws/telemetry")` — EMQX-д paho-mqtt-ээр захиалж, ирсэн мессежийг клиент рүү түлхэх

(б) нь энэ архитектурт илүү шууд: 🥧 Pi-гийн агент → гүүр → EMQX → API → хөтөч. Дараа нь хэмжинэ:

```bash
python3 - <<'EOF'
import json, time, websocket        # pip install websocket-client
ws = websocket.create_connection("ws://localhost:8000/ws/telemetry")
t0, n, b = time.time(), 0, 0
while time.time() - t0 < 60:
    m = ws.recv(); n += 1; b += len(m)
ws.close()
print(f"{n} мессеж, {b} байт, 60 сек")
EOF
```

#### Хүснэгт 7.5 — Polling ба WebSocket (60 секунд, 5 төхөөрөмж)

| | 1 сек polling | WebSocket |
|---|---|---|
| Хүсэлт / холболтын тоо | | 1 |
| Нийт байт | | |
| Шинэчлэлийн дундаж саатал (мс) | | |

---

### Алхам 6 — АЮУЛГҮЙ БАЙДЛЫН ШАЛГАЛТ (30 мин) 💻

`security_tests.py` нь **9 шалгалт** ажиллуулна. Анхаар: `--tb` тугийг `--registry` **орлосон** — ThingsBoard энэ архитектурт байхгүй.

```bash
mkdir -p lab07/out
python3 lab07/security_tests.py --api http://localhost:8000 \
    --influx http://localhost:8181 --registry http://localhost:8090 \
    --json lab07/out/security-before.json
```

Гаралт **хоёр бүлэгт** тусгаарлагдана:

- **САНААТАЙ ЭМЗЭГ БАЙДАЛ** — `main.py`-ийн `decode_token`-д зориудаар үлдээсэн. **ЯГ 2** байх ёстой; өөр тоо гарвал шалгалт эсвэл API буруу ажиллаж байна.
- **Дэд бүтцийн ноцтой олдвор** — код биш, тохиргоо. Танилтгүй InfluxDB бол **бодит** асуудал, гэхдээ "тэр хоёрын" нэг **биш**. Энэ ялгааг тайланд заавал хадгал.

**Гараар давтаж батал** — гарын үсгийн шалгалт:

```bash
python3 - <<'EOF'
import base64, json, time, httpx
b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b'=').decode()
sig = base64.urlsafe_b64encode(b'not-a-real-signature').rstrip(b'=').decode()
evil = f"{b({'alg':'RS256','typ':'JWT'})}.{b({'sub':'attacker','groups':['admin'],'exp':time.time()+3600})}.{sig}"
r = httpx.post("http://localhost:8000/graphql", json={"query": "{ whoami }"},
               headers={"Authorization": f"Bearer {evil}"})
print(r.json())
EOF
```

`roles=admin` гэж гарвал — **та ямар ч нууц үггүйгээр админ боллоо**.

Хугацаа дууссан токеныг ч давт (`'exp': time.time() - 7200`) — мөн адил `admin` гарах ёстой. Гурав дахь халдлага: 200 давхар нэрлэсэн (`a0: devices(limit:50){name} a1: … a199: …`) талбартай нэг асуулга — `security_tests.py` үүнийг өөрөө үүсгэж илгээдэг, гаралтын хугацааг тэмдэглэ.

#### Хүснэгт 7.6 — Аюулгүй байдлын 9 шалгалтын бүртгэл ⭐

| # | Шалгалт | Зэрэглэл | Санаатай уу | Өмнө | Хэрхэн гараар батлав | Засвар | Дараа |
|---|---|---|---|---|---|---|---|
| 1 | Анонимоор төхөөрөмж жагсаах татгалзсан | high | ✗ | | | | |
| 2 | Хуурамч гарын үсэгтэй токен татгалзсан | **critical** | **✓** | | | | |
| 3 | viewer тушаал илгээхийг татгалзсан | high | ✗ | | | | |
| 4 | Хугацаа дууссан токен татгалзсан | **high** | **✓** | | | | |
| 5 | Introspection хаагдсан | low | ✓ | | | | |
| 6 | Асуулгын нийлмэл байдлын хязгаар | medium | ✓ | | | | |
| 7 | Тарилгын оролдлого аюулгүй боловсруулагдсан | high | ✗ | | | | |
| 8 | InfluxDB танилтгүй уншигдана | high | ✗ (дэд бүтэц) | | | | |
| 9 | Бүртгэл танилтгүй уншигдана | medium | ✗ (дэд бүтэц) | | | | |

---

### Алхам 7 — ЗАСАХ ба дахин шалгах (45 мин) 💻

**7.1 Гарын үсэг ба хугацааны шалгалт** (санаатай эмзэг байдал #1). `jwt.get_unverified_claims(token)` мөрийг солино:

```python
_JWKS = None
def _jwks():
    global _JWKS
    if _JWKS is None:
        _JWKS = httpx.get(f"{OIDC_ISSUER}/keys", timeout=10).json()
    return _JWKS

def decode_token(token: str) -> Principal:
    from jose import jwt
    claims = jwt.decode(token, _jwks(),
        algorithms=["RS256"],                 # ← ЗААВАЛ заана
        audience="cnc302", issuer=OIDC_ISSUER,
        options={"verify_exp": True, "verify_aud": True})
    roles = claims.get("groups") or claims.get("roles") or ["viewer"]
    ...
```

> **`algorithms=["RS256"]`-ийг заавал заа.** Заахгүй бол халдагч `alg: none` (гарын үсэггүй) эсвэл `alg: HS256` (нийтийн түлхүүрийг нууц болгон ашиглах) халдлага хийж болно. Энэ бол JWT-ийн сонгодог эмзэг байдал. `verify_exp` нь #2-р шалгалтыг (хугацаа) нэг зэрэг хаана.

**7.2 Introspection ба нийлмэл байдал** (санаатай эмзэг байдал #2):

```python
import os
from strawberry.extensions import AddValidationRules, QueryDepthLimiter
from graphql.validation import NoSchemaIntrospectionCustomRule

exts = [QueryDepthLimiter(max_depth=6)]
if os.environ.get("ENV") == "production":
    exts.append(AddValidationRules([NoSchemaIntrospectionCustomRule]))
schema = strawberry.Schema(query=Query, mutation=Mutation, extensions=exts)
```

> `QueryDepthLimiter` нь **гүнийг** хязгаарлана, харин шалгалт №6 нь **өргөнийг** (200 alias) шалгаж байгааг анзаар. Гүнээс гадна талбарын тоог хязгаарлах хэрэгтэй — тайландаа энэ ялгааг бич.

**7.3 SQL мөр залгалт.** `Device.readings` дотор `self.name` шууд SQL-д залгагдаж байна. Хамгийн багадаа шалга: `if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.name): raise ValueError(...)`. (`Query.device` нь харин Python дээр шүүдэг тул тарилгын гадаргуугүй — яагаад болохыг тайланд бич.)

**7.4 Дахин барьж, дахин шалгана:**

```bash
docker compose --profile app up -d --build graphql-api
sleep 10
python3 lab07/security_tests.py --api http://localhost:8000 \
    --influx http://localhost:8181 --registry http://localhost:8090 \
    --json lab07/out/security-after.json
```

**Хүлээгдэх:** `✓ Санаатай эмзэг байдал илрээгүй — засвар ажиллаж байна.` Хуучин токен ажиллахаа болино — `tok`-оор шинийг ав. Бүх токен татгалзвал `aud`/`iss` таарахгүй байна: issuer нь `http://dex:5556/dex` (контейнер доторх нэр) тул `OIDC_ISSUER` мөн тэр утгатай байх ёстой.

**7.5 RBAC-ыг бодитоор турш:**

```bash
for U in viewer operator admin; do
  echo "── $U ──"
  curl -s -X POST localhost:8000/graphql -H "Authorization: Bearer $(tok $U)" \
    -H 'Content-Type: application/json' \
    -d '{"query":"mutation { sendCommand(device:\"dev0001\", command:\"reboot\") }"}' | jq -c
done
```

#### Хүснэгт 7.7 — RBAC матриц

| Үйлдэл | viewer | operator | admin | Бодитоор туршсан үр дүн |
|---|---|---|---|---|
| `devices` жагсаах | ✓ | ✓ | ✓ | |
| `readings` унших | ✓ | ✓ | ✓ | |
| `sendCommand` | ✗ | ✓ | ✓ | |
| Төхөөрөмж үүсгэх / устгах | ✗ | ✗ | ✓ | |
| Бүртгэлд шууд хандах (:8090) | ? | ? | ? | |

Сүүлийн мөр нь **defence in depth**-ийн асуулт: RBAC зөвхөн GraphQL давхаргад л байгаа бол хэн ч :8090 руу шууд хандаж чадна.

---

### Алхам 8 — InfluxDB `--without-auth` ба Zero Trust (10 мин) 💻

Энэ курс эхнээс нь InfluxDB-г танилтгүй ажиллуулж ирсэн. Яагаад, ямар үнээр:

```bash
curl -s -X POST localhost:8181/api/v3/query_sql -H 'Content-Type: application/json' \
  -d '{"db":"cnc302","q":"SELECT count(*) FROM telemetry","format":"json"}' | jq
```

#### Хүснэгт 7.8 — Засварын өмнөх/дараах дүн

| | Өмнө (`security-before.json`) | Дараа (`security-after.json`) |
|---|---|---|
| ТЭНЦСЭН | | |
| АНХААР | | |
| УНАСАН | | |
| `deliberate_criticals` | **2** | **0** |
| `infra_criticals` | | |

**Тайландаа заавал хариул:** яагаад `--without-auth` нь лабораторид зөвшөөрөгдөх, гэхдээ үйлдвэрлэлд болохгүй вэ? Zero Trust бол юуг шаардах байсан бэ — гурав нэрлэ (жишээ: үйлчилгээ бүрт өөрийн таних тэмдэг, mTLS эсвэл токен, хамгийн бага эрхийн зарчим, хандалтын аудит лог).

---

### Алхам 9 — Git commit (5 мин)

```bash
cd ~/cnc302 && git add lab07/ stack/dex/
git commit -m "Лаб 7: GraphQL давхарга, OIDC, хоёр эмзэг байдал засагдсан"
git tag lab07-done && git push && git push --tags

# ⚠ Нууц ороогүйг ЗААВАЛ шалга — хоёулаа хоосон байх ЁСТОЙ
git ls-files | grep -E '\.env$|\.key$|devices\.csv'
grep -rn 'eyJ' lab07/out/ | head          # JWT-г тайланд бүү үлдээ
```

---

## 5. Хяналтын асуултууд

Хариулт бүр **хүснэгтээс тоо иш татсан** байх ёстой.

1. Хүснэгт 7.3-д 50 төхөөрөмж дээр REST ба GraphQL-ийн хугацааны ялгаа хэдэн мс байв? Сүлжээний RTT 200 мс байсан бол REST хэдэн секунд болох вэ (51 × RTT)? GraphQL хэд вэ?

2. Хүснэгт 7.4-т нэгтгэлийг InfluxDB дээр хийхэд хэдэн дахин хурдан байв, татсан мөрийн тоо хэдэн дахин багассан бэ? 30 хоногийн өгөгдөл дээр энэ харьцаа хэрхэн өөрчлөгдсөн бэ?

3. Хүснэгт 7.5-д polling ба WebSocket-ийн байтын ялгаа хэд байв? 1000 хэрэглэгчтэй үед polling серверт хэдэн хүсэлт/секунд өгөх вэ?

4. Хүснэгт 7.6-д **санаатай** эмзэг байдал хэд байв, **дэд бүтцийн** олдвор хэд байв? Эдгээрийг яагаад ялгаж дүгнэх шаардлагатай вэ? (Санамж: аль нь код засаж, аль нь тохиргоо засаж шийдэгддэг вэ.)

5. `algorithms=["RS256"]`-ийг заахгүй бол ямар хоёр халдлага боломжтой болох вэ? `alg: none` ба `alg: HS256` халдлагыг тус тус тайлбарла.

6. Токеныг цуцлах (revoke) хэрхэн ажилладаг вэ? JWT нь **төлөвгүй** тул энэ яагаад хэцүү вэ? Лаб 2-ын сертификат цуцлалт (Хүснэгт 2.7) болон MQTT session цуцлалттай ямар төстэй вэ?

7. Хүснэгт 7.7-гийн сүүлийн мөр: `viewer` эрхтэй хэрэглэгч :8090 эсвэл :8181 руу шууд хандаж чадвал RBAC ямар утгатай вэ? Zero Trust-д үүнийг хэрхэн хаах вэ (Хүснэгт 7.8-ын гурван шаардлагыг иш тат)?

---

## 6. Хүлээлгэн өгөх зүйл

| # | Зүйл | Байрлал |
|---|---|---|
| 1 | Тайлан (Хүснэгт 7.1–7.8 бөглөсөн) | `lab07/report.md` → PDF |
| 2 | Шалгалтын өмнөх/дараах JSON | `lab07/out/security-before.json`, `security-after.json` |
| 3 | `decode_token` ба схемийн засвар (diff хэлбэрээр) | тайлангийн хавсралт |
| 4 | `deviceStats` ба WebSocket/subscription хэрэгжүүлэлт | `lab07/graphql-api/main.py` |
| 5 | Git tag | `lab07-done` |

---

## 7. Үнэлгээний шалгуур (10 оноо)

| Шалгуур | Оноо |
|---|---|
| REST/GraphQL харьцуулалт хэмжигдэж, `deviceStats` хэрэгжсэн | 2 |
| OIDC нэвтрэлт ажиллаж, үүргийн эх сурвалж шийдэгдсэн | 1 |
| Хоёр санаатай эмзэг байдал олдож, **гараар** батлагдсан | 2 |
| Засвар кодод хэрэгжиж, `security-after` дээр `deliberate_criticals = 0` | 3 |
| WebSocket / subscription ажиллаж, Хүснэгт 7.5 бөглөгдсөн | 1 |
| RBAC матриц бодитоор туршсан, Zero Trust дүгнэлт үндэслэлтэй | 1 |

**Автомат 0 оноо:** засварыг зөвхөн тайланд бичээд кодод хэрэгжүүлээгүй бол.

---

## 8. Түгээмэл алдаа

| Шинж | Шалтгаан | Шийдэл |
|---|---|---|
| `graphql-api` эхлэхгүй | build алдаа | `docker compose logs graphql-api` |
| `{ devices }` → эрх байхгүй | токенгүй хүсэлт | Алхам 2-оор токен ав |
| Dex `password` grant татгалзана | grant идэвхгүй | `passwordConnector: local`, эсвэл code flow |
| `whoami` үргэлж `viewer` | Dex статик хэрэглэгчид `groups` байхгүй | Алхам 2.3–2.4 |
| JWKS татагдахгүй | `OIDC_ISSUER` буруу | контейнер дотроос `http://dex:5556/dex` байх ёстой |
| `readings` хоосон | 🥧 агент зогссон / гүүр тасарсан | 🥧 `make link` → `bridge/state 1` |
| Шалгалт "санаатай 0" гэнэ (засварын өмнө) | API дахин баригдаагүй | `up -d --build graphql-api` |
