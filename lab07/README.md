# Лаб 7 — Хэрэглээний давхарга ба аюулгүй байдлын шалгалт

| | |
|---|---|
| **7 хоног** | XIV |
| **Хугацаа** | 4 цаг |
| **Суралцахуйн үр дүн** | ҮД3 (үнэлэх), ҮД4 (зохиох), ҮД6 |
| **Үнэлгээ** | Бичгийн тайлан, 10 оноо |

---

## 1. Зорилго

Платформын дээр **хэрэглэгчийн давхаргыг** барьж, дараа нь түүнийг **эвдэхийг оролдоно**.

Хоёр хэсэг:

1. **Барих** — REST ба GraphQL-ийн ялгааг зохион бүтээх замаар ойлгох, WebSocket-оор бодит хугацааны шинэчлэл, Dex-ээр OIDC нэвтрэлт, RBAC үүрэг
2. **Эвдэх** — `security_tests.py`-г ажиллуулж эмзэг байдлыг олох, засах, дахин шалгах

> **Чухал:** `graphql-api/main.py` дотор **зориудын эмзэг байдал** байгаа. Таны ажил бол түүнийг олж засах явдал. Лабораторийн эцэст `security_tests.py` бүх шалгалтад тэнцэх ёстой.

---

## 2. Урьдчилсан нөхцөл

- Лаб 1–6 дууссан
- Бие даалт XIV: OAuth2/OIDC-ийн урсгалыг уншсан (authorization code flow)

```bash
cd ~/cnc302/stack
docker compose --profile core --profile pipeline --profile app up -d --build
make health
docker compose logs --tail=30 graphql-api dex
```

Шалгах:
```bash
curl -s http://localhost:8000/health | jq
curl -s http://localhost:5556/dex/.well-known/openid-configuration | jq .issuer
```

---

## 3. Онолын сануулга

**REST-ийн 1+N асуудал.** 50 төхөөрөмж бүрийн сүүлийн 20 хэмжилтийг авахад REST-д **51 хүсэлт** хэрэгтэй (1 жагсаалт + 50 хэмжилт). GraphQL-д **1 хүсэлт**. IoT-д энэ нь жижиг зүйл биш: гар утасны апп сул сүлжээгээр 51 удаа тойрч гүйхэд хэдэн секунд алдана.

**Гэхдээ GraphQL шинэ эрсдэл авчирна.** Клиент асуулгын хэлбэрийг өөрөө тодорхойлдог тул нэг хүсэлтээр серверийг унагаах боломжтой (гүн үүрлэсэн эсвэл олон давхар нэрлэсэн асуулга). REST-д ийм зүйл байхгүй, учир нь төгсгөлийн цэг бүр тогтмол өртөгтэй.

**Танилт (authentication) ≠ Эрх (authorization).**
- Танилт: *чи хэн бэ?* → OIDC токен
- Эрх: *чи юу хийж болох вэ?* → RBAC үүрэг

Хамгийн түгээмэл эмзэг байдал бол эхнийхийг хийгээд хоёр дахийг мартах, эсвэл **токеныг шалгалгүй итгэх**.

**Zero Trust.** "Дотоод сүлжээ тул аюулгүй" гэсэн таамаг байхгүй. Хүсэлт бүрийг шалгана — эх сурвалж хаанаас ирсэн нь хамаагүй. Энэ лабораторид InfluxDB `--without-auth` горимд ажиллаж байгаа нь яг энэ зарчмыг зөрчиж байгаа жишээ.

---

## 4. Алхмууд

### Алхам 1 — GraphQL ба REST-ийн харьцуулалт (55 мин)

**1.1** GraphiQL-ийг хөтчөөр нээнэ: `http://localhost:8000/graphql`

Туршиж үзнэ:

```graphql
{ whoami }

{ devices(limit: 5) { id name type } }

{
  devices(limit: 5) {
    name
    readings(limit: 10) { time temperature vibrationRms }
  }
}
```

**1.2 Хүсэлтийн тоог хэмжинэ.** REST-ээр ижил өгөгдөл авах:

```bash
# 1-р хүсэлт: жагсаалт
curl -s localhost:8000/rest/devices?limit=5 | jq -r '.devices[].name' > /tmp/devs.txt

# дараагийн N хүсэлт: тус бүрийн хэмжилт
time (while read d; do
  curl -s -X POST localhost:8181/api/v3/query_sql -H 'Content-Type: application/json' \
    -d "{\"db\":\"cnc302\",\"q\":\"SELECT * FROM telemetry WHERE device='$d' ORDER BY time DESC LIMIT 10\",\"format\":\"json\"}" > /dev/null
done < /tmp/devs.txt)
```

GraphQL-ээр:
```bash
time curl -s -X POST localhost:8000/graphql -H 'Content-Type: application/json' \
  -d '{"query":"{ devices(limit:5){ name readings(limit:10){ time temperature } } }"}' > /dev/null
```

**Хүснэгт 1**-ийг бөглөнө: хүсэлтийн тоо, нийт хугацаа, дамжуулсан байт.

**1.3 50 төхөөрөмж дээр давтана.** Ялгаа өсөв үү? Шугаман уу?

**1.4 ОЮУТНЫ ДААЛГАВАР.** `main.py` дотор `# TODO(оюутан)` гэсэн `deviceStats` талбарыг хэрэгжүүлнэ:

```graphql
{ deviceStats(device: "dev0001", hours: 24) { avg min max samples } }
```

Нэгтгэлийг **InfluxDB-д хийлгэнэ** (SQL-ийн `avg/min/max`), Python дээр биш. Яагаад? Хүснэгт 1-д хоёуланг нь хэмжиж хариулна.

```bash
docker compose --profile app up -d --build graphql-api
```

---

### Алхам 2 — WebSocket бодит хугацааны шинэчлэл (30 мин)

ThingsBoard нь WebSocket API-тай. Дэлгэц шинэчлэхийн тулд байнга асуух (polling) шаардлагагүй.

```bash
python3 - <<'EOF'
import json, websocket    # pip install websocket-client
TOKEN = "<ThingsBoard-ийн JWT — /api/auth/login-ээс>"
DEVICE_ID = "<төхөөрөмжийн UUID>"
ws = websocket.create_connection(
    f"ws://localhost:8080/api/ws/plugins/telemetry?token={TOKEN}")
ws.send(json.dumps({"tsSubCmds":[{"entityType":"DEVICE","entityId":DEVICE_ID,
        "scope":"LATEST_TELEMETRY","cmdId":1}],"historyCmds":[],"attrSubCmds":[]}))
for _ in range(20):
    print(ws.recv()[:160])
ws.close()
EOF
```

**Хүснэгт 2**-ыг бөглөнө: 1 секундын polling ба WebSocket-ийн харьцуулалт (хүсэлтийн тоо, дамжуулсан байт, шинэчлэлийн саатал).

---

### Алхам 3 — OIDC нэвтрэлт (Dex) (45 мин)

**3.1 Токен авах.** Dex-ийн нууц үгийн урсгалаар (лабораторид хялбар):

```bash
curl -s -X POST http://localhost:5556/dex/token \
  -d grant_type=password -d scope='openid email profile groups' \
  -d client_id=cnc302 -d client_secret=cnc302-lab-secret \
  -d username=viewer@cnc302.mn -d password=cnc302 | jq
```

> `password` grant ажиллахгүй бол Dex-ийн `staticClients` дотор `public: true` нэмэх, эсвэл authorization code урсгалыг ашиглана. Аль нь болсныг тайландаа тэмдэглэ — **энэ өөрөө сургамжтай**: OAuth2-ын урсгал бүр өөр аюулгүй байдлын шинжтэй.

**3.2 Токеныг API-д ашиглах:**

```bash
TOKEN=$(curl -s -X POST http://localhost:5556/dex/token \
  -d grant_type=password -d scope='openid email profile groups' \
  -d client_id=cnc302 -d client_secret=cnc302-lab-secret \
  -d username=admin@cnc302.mn -d password=cnc302 | jq -r .id_token)

curl -s -X POST localhost:8000/graphql -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"query":"{ whoami }"}' | jq
```

**3.3 Асуудлыг олох.** `whoami` ямар үүрэг харуулж байна вэ? Dex-ийн статик хэрэглэгчид `groups` талбар **байхгүй**. Тиймээс бүгд `viewer` болно.

**Хоёр шийдлийг харьцуул (Хүснэгт 3):**
- (а) Dex-ийг LDAP/GitHub холбогчтой болгох → бодит бүлэг ирнэ
- (б) GraphQL API дээр имэйлээс үүрэг зурвасжуулах (`admin@` → `admin`)

Аль нь илүү зөв вэ? Аль нь илүү хурдан вэ? Аль нь үйлдвэрлэлд тохирох вэ?

**3.4** Сонгосон шийдлээ хэрэгжүүлнэ.

---

### Алхам 4 — АЮУЛГҮЙ БАЙДЛЫН ШАЛГАЛТ (35 мин)

```bash
python3 lab07/security_tests.py --api http://localhost:8000 \
    --influx http://localhost:8181 --tb http://localhost:8080 \
    --json lab07/out/security-before.json
```

**Хоёр ноцтой асуудал гарах ёстой.** Гарахгүй бол шалгалт буруу ажиллаж байна.

Гарсан бүр асуудлыг **гараар давтаж** батална. Жишээ нь гарын үсгийн шалгалт:

```bash
python3 - <<'EOF'
import base64, json, httpx
b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b'=').decode()
sig = base64.urlsafe_b64encode(b'garbage').rstrip(b'=').decode()
evil = f"{b({'alg':'RS256','typ':'JWT'})}.{b({'sub':'attacker','groups':['admin']})}.{sig}"
r = httpx.post("http://localhost:8000/graphql",
               json={"query":"{ whoami }"},
               headers={"Authorization": f"Bearer {evil}"})
print(r.json())
EOF
```

Хэрэв `roles=admin` гэж гарвал — **та ямар ч нууц үггүйгээр админ боллоо**.

**Хүснэгт 4** (эмзэг байдлын бүртгэл)-ийг бөглөнө.

---

### Алхам 5 — ЗАСАХ (45 мин)

**5.1 Гарын үсгийн шалгалт.** `main.py`-ийн `decode_token`-ыг засна:

```python
import httpx
from jose import jwt

_JWKS = None

def _jwks():
    global _JWKS
    if _JWKS is None:
        _JWKS = httpx.get(f"{OIDC_ISSUER}/keys", timeout=10).json()
    return _JWKS

def decode_token(token: str) -> Principal:
    claims = jwt.decode(
        token, _jwks(),
        algorithms=["RS256"],
        audience="cnc302",
        issuer=OIDC_ISSUER,
        options={"verify_exp": True, "verify_aud": True},
    )
    ...
```

> **Анхаар:** `algorithms=["RS256"]`-ийг заавал заана. Заахгүй бол халдагч `alg: none` эсвэл `alg: HS256` (нийтийн түлхүүрийг нууц болгон ашиглах) халдлага хийж болно. Энэ бол JWT-ийн сонгодог эмзэг байдал.

**5.2 Хугацааны шалгалт** — `verify_exp: True`-аар шийдэгдэнэ.

**5.3 Introspection хаах** (үйлдвэрлэлийн горимд):

```python
from strawberry.extensions import AddValidationRules
from graphql.validation import NoSchemaIntrospectionCustomRule
schema = strawberry.Schema(query=Query, mutation=Mutation,
    extensions=[AddValidationRules([NoSchemaIntrospectionCustomRule])]
                if os.environ.get("ENV") == "production" else [])
```

**5.4 Асуулгын нийлмэл байдлыг хязгаарлах:**

```python
from strawberry.extensions import QueryDepthLimiter
# extensions=[QueryDepthLimiter(max_depth=6), ...]
```

**5.5 Мөр залгалтаас параметржүүлсэн асуулга руу.** `influx_sql`-д хэрэглэгчийн оруулсан утгыг шууд SQL-д залгаж байна. Хамгийн багадаа `device` нэрийг шалгах:

```python
import re
if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", name):
    raise ValueError("төхөөрөмжийн нэр буруу")
```

**5.6 InfluxDB-д танилт нэмэх** (сонголтоор, цаг байвал): `--without-auth` тугийг хасаж админ токен үүсгэнэ.

**5.7 Дахин шалгана:**

```bash
docker compose --profile app up -d --build graphql-api
python3 lab07/security_tests.py --api http://localhost:8000 \
    --json lab07/out/security-after.json
```

**Бүх ноцтой шалгалт ТЭНЦСЭН байх ёстой.**

---

### Алхам 6 — RBAC матриц ба тайлан (30 мин)

**Хүснэгт 5**-ыг бөглөнө. Дараа нь гурван үүргээр бодитоор туршина:

```bash
for U in viewer operator admin; do
  T=$(curl -s -X POST http://localhost:5556/dex/token -d grant_type=password \
      -d scope='openid email profile groups' -d client_id=cnc302 \
      -d client_secret=cnc302-lab-secret -d username=$U@cnc302.mn \
      -d password=cnc302 | jq -r .id_token)
  echo "── $U ──"
  curl -s -X POST localhost:8000/graphql -H "Authorization: Bearer $T" \
    -H 'Content-Type: application/json' \
    -d '{"query":"mutation { sendCommand(device:\"dev0001\", command:\"reboot\") }"}' | jq -c
done
```

```bash
git add -A && git commit -m "Лаб 7: GraphQL давхарга, OIDC, аюулгүй байдлын засвар"
git tag lab07-done && git push origin main --tags
```

---

## 5. Хэмжилтийн хүснэгтүүд

### Хүснэгт 1 — REST ба GraphQL

| Хэмжилт | REST | GraphQL |
|---|---|---|
| 5 төхөөрөмж + хэмжилт: хүсэлтийн тоо | | 1 |
| 5 төхөөрөмж: нийт хугацаа (мс) | | |
| 50 төхөөрөмж: хүсэлтийн тоо | | 1 |
| 50 төхөөрөмж: нийт хугацаа (мс) | | |
| Дамжуулсан байт (5 төхөөрөмж) | | |
| Илүүдэл өгөгдөл (over-fetching) байна уу | | |

`deviceStats` нэгтгэл: InfluxDB дээр ______ мс, Python дээр ______ мс. Яагаад ялгаатай: ____________

### Хүснэгт 2 — Polling ба WebSocket

| | 1с polling | WebSocket |
|---|---|---|
| Хүсэлт/минут | 60 | |
| Байт/минут | | |
| Шинэчлэлийн саатал (дундаж) | | |
| Сервер талын ачаалал | | |

### Хүснэгт 3 — Үүргийн эх сурвалжийн сонголт

| | (а) Dex холбогч (LDAP/GitHub) | (б) API дээр имэйлээс зурвасжуулах |
|---|---|---|
| Хэрэгжүүлэх хугацаа | | |
| Үүргийг хаана удирдах вэ | | |
| Шинэ хэрэглэгч нэмэхэд | | |
| Үйлдвэрлэлд тохирох уу | | |
| **Бидний сонголт ба шалтгаан** | | |

### Хүснэгт 4 — Эмзэг байдлын бүртгэл ⭐

| # | Эмзэг байдал | Ноцтой байдал | Хэрхэн батлав | Үр дагавар | Засвар | Дахин шалгалт |
|---|---|---|---|---|---|---|
| 1 | Токены гарын үсэг шалгагдаагүй | critical | | | | |
| 2 | Хугацаа дууссан токен хүлээн авагдана | high | | | | |
| 3 | Introspection нээлттэй | low | | | | |
| 4 | Асуулгын нийлмэл байдал хязгааргүй | medium | | | | |
| 5 | SQL мөр залгалтаар үүсгэгддэг | high | | | | |
| 6 | InfluxDB танилтгүй | high | | | | |

### Хүснэгт 5 — RBAC матриц

| Үйлдэл | viewer | operator | admin | Бодитоор туршсан үр дүн |
|---|---|---|---|---|
| Төхөөрөмж жагсаах | ✓ | ✓ | ✓ | |
| Телеметр унших | ✓ | ✓ | ✓ | |
| Тушаал илгээх | ✗ | ✓ | ✓ | |
| Төхөөрөмж үүсгэх | ✗ | ✗ | ✓ | |
| Төхөөрөмж устгах | ✗ | ✗ | ✓ | |
| OTA тараах (Лаб 2) | ✗ | ? | ✓ | |

---

## 6. Хяналтын асуулт

1. 50 төхөөрөмж дээр REST ба GraphQL-ийн хугацааны ялгаа хэд байв? Сүлжээний саатал 200 мс байсан бол ялгаа хэрхэн өөрчлөгдөх вэ?
2. GraphQL ямар шинэ довтолгооны гадаргуу нэмэв? REST-д яагаад тэр асуудал байхгүй вэ?
3. `algorithms=["RS256"]`-ийг заахгүй бол ямар халдлага боломжтой болох вэ? (`alg: none`, `alg: HS256` халдлагыг тайлбарла.)
4. Танилт ба эрхийн ялгааг өөрийн жишээгээр тайлбарла. Аль нэгийг нь мартвал юу болох вэ?
5. Токеныг цуцлах (revoke) хэрхэн ажилладаг вэ? JWT нь **төлөвгүй** тул энэ яагаад хэцүү вэ? Лаб 2-ын сертификат цуцлалттай ямар төстэй вэ?
6. InfluxDB `--without-auth` горимд ажиллаж байгаа нь Zero Trust-ын аль зарчмыг зөрчиж байна вэ?
7. Хэрэглэгч `viewer` эрхтэй боловч InfluxDB-д шууд хандаж чадвал RBAC ямар утгатай вэ? (Санамж: **defence in depth**.)
8. Асуулгын нийлмэл байдлын хязгаарыг хэрхэн тогтоох вэ? Хэт бага бол юу болох вэ?

---

## 7. Тайлангийн шаардлага

- [ ] Хүснэгт 1–5 бүрэн
- [ ] `security-before.json` ба `security-after.json` — өмнөх/дараах харьцуулалт
- [ ] `decode_token`-ийн засварласан код (diff хэлбэрээр)
- [ ] `deviceStats` талбарын хэрэгжүүлэлт
- [ ] Гурван үүргээр туршсан гаралт
- [ ] Хяналтын 8 асуултын хариулт
- [ ] Git tag `lab07-done`

---

## 8. Оношилгоо

| Шинж тэмдэг | Шалтгаан | Шийдэл |
|---|---|---|
| `graphql-api` эхлэхгүй | build алдаа | `docker compose logs graphql-api` |
| `/health` degraded | ThingsBoard/InfluxDB унтарсан | `make health` |
| Dex `password` grant татгалзана | grant идэвхгүй | `staticClients`-д `public: true` эсвэл code flow |
| `whoami` үргэлж viewer | Dex статик хэрэглэгчид groups байхгүй | Алхам 3.3 |
| Засварын дараа бүх токен татгалзана | `audience`/`issuer` таарахгүй | токенийг задлан `aud`, `iss`-ийг хар |
| `security_tests.py` холбогдохгүй | буруу `--api` | `curl localhost:8000/health` |
| JWKS татахгүй | `OIDC_ISSUER` контейнер дотроос `dex:5556` байх ёстой | орчны хувьсагчийг шалга |

---

## 9. Үнэлгээний шалгуур (10 оноо)

| Шалгуур | Оноо |
|---|---|
| GraphQL ба REST харьцуулалт хэмжигдсэн, `deviceStats` хэрэгжсэн | 2 |
| OIDC нэвтрэлт ажиллаж, үүргийн эх сурвалж шийдэгдсэн | 2 |
| Эмзэг байдал олдож, гараар батлагдсан | 2 |
| Гарын үсэг ба хугацааны шалгалт засагдаж, `security-after` цэвэр | 3 |
| RBAC матриц бодитоор туршсан үр дүнтэй | 1 |

**Автомат 0 оноо:** засварыг зөвхөн тайланд бичээд кодод хэрэгжүүлээгүй бол.
