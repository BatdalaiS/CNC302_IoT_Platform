# Raspberry Pi 5 (8 GB) — нөөцийн төсөв

Энэ хүснэгт нь **чиглүүлэх тооцоо**. Бодит утгыг Лаб 1-д өөрсдөө хэмжинэ.

| Үйлчилгээ | Профайл | Compose хязгаар | Хүлээгдэх амралтын хэрэглээ | Тэмдэглэл |
|---|---|---|---|---|
| emqx | core | 1024 MiB | 150–250 MiB | Холболт нэмэгдэхэд өснө (~4 KiB/холболт) |
| thingsboard | core | 2500 MiB | 1200–1800 MiB | JVM + Postgres нэг контейнерт |
| influxdb | core | 1024 MiB | 250–500 MiB | Бичилтийн ачаалалтай өснө |
| grafana | core | 512 MiB | 120–200 MiB | Самбарын тоогоор өснө |
| nodered | pipeline | 512 MiB | 120–200 MiB | Урсгалын нарийвчлалаас хамаарна |
| dex | app | 256 MiB | 30–60 MiB | |
| graphql-api | app | 512 MiB | 80–150 MiB | Python/FastAPI |
| ollama | ai | 3072 MiB | загвараас хамаарна | 1.5B загвар ≈ 1.2–2 GiB |

## Профайлын нийлбэр

| Хослол | Хязгаарын нийлбэр | Практикт | Дүгнэлт |
|---|---|---|---|
| core | 5.0 GiB | 1.7–2.7 GiB | Лаб 1–4-т тохиромжтой |
| core + pipeline | 5.5 GiB | 1.9–2.9 GiB | Лаб 5 |
| core + pipeline + app | 6.3 GiB | 2.0–3.1 GiB | Лаб 7 |
| бүгд + ai | 9.4 GiB | **8 GiB давна** | Лаб 8-д зарим үйлчилгээг зогсооно |

## Лаб 8-ын зөвлөмж

```bash
docker compose stop nodered grafana dex graphql-api
docker compose --profile ai up -d ollama
ollama pull qwen2.5:1.5b        # 3B-ээс дээш загвар Pi дээр хэт удаан
```

## Санамж

- **Swap 2 GB заавал.** Үгүй бол ThingsBoard эхлэхдээ OOM болно.
- `deploy.resources.limits` нь хязгаар л тавьдаг, нөөц **баталгаажуулдаггүй**.
- `docker stats`-ын санах ойн тоо зөв гарахад `cgroup_enable=memory` хэрэгтэй.
- Идэвхтэй хөргөлт байхгүй бол Pi 5 ачаалал дор 80 °C давж, давтамжаа бууруулна — бүх хэмжилт гажина. `vcgencmd get_throttled` нь `0x0` байх ёстой.
