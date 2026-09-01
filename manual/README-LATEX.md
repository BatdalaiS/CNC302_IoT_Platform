# CNC302 — Лабораторийн гарын авлага (LaTeX хувилбар)

Энэ сан нь `CNC302-labs/` доторх найман лабораторийн Markdown зааврыг
нэг **68 хуудас PDF гарын авлага** болгон хөрвүүлнэ.

## Хурдан эхлэх

```bash
# 1. Шаардлагатай зүйлс (Debian/Ubuntu)
sudo apt install texlive-xetex texlive-latex-extra texlive-fonts-extra \
                 fonts-dejavu pandoc python3 latexmk

# 2. Хөрвүүлэх
make                    # Markdown → .tex → PDF
```

Гаралт: `main.pdf`

## Шаардлага

| Хэрэгсэл | Хувилбар | Юунд |
|---|---|---|
| XeLaTeX | TeX Live 2021+ | кирилл үсэг (fontspec) |
| pandoc | 3.0+ | Markdown → LaTeX |
| Python | 3.9+ | `build.py` |
| DejaVu фонт | — | Serif / Sans / Sans Mono |

> **Кирилл үсэг:** pdfLaTeX-ээр хөрвүүлж БОЛОХГҮЙ. XeLaTeX эсвэл LuaLaTeX
> шаардлагатай. DejaVu фонт байхгүй бол `preamble.tex`-ийн `\setmainfont`
> мөрүүдийг өөрийн кирилл дэмждэг фонтоор солино (жишээ нь Liberation,
> Noto Serif, Times New Roman).

## Файлын бүтэц

```
CNC302-labs-latex/
├── main.tex           ← үндсэн файл (гарчгийн хуудас, агуулга, бүлгүүд)
├── preamble.tex       ← фонт, өнгө, хүснэгт, кодын блок, гарчгийн загвар
├── highlighting.tex   ← pandoc-ийн синтакс өнгөлөлтийн макронууд
├── build.py           ← Markdown → LaTeX хөрвүүлэгч
├── Makefile
└── chapters/          ← АВТОМАТААР ҮҮСГЭГДДЭГ — гараар засахгүй!
    ├── 00-intro.tex … 13-k3s.tex
```

> ⚠ `chapters/*.tex` файлууд `build.py`-аар автоматаар үүсдэг. Агуулгыг
> засах бол **эх Markdown файлыг** (`CNC302-labs/labNN/README.md`) засаад
> `make tex` ажиллуулна. Загварыг засах бол `preamble.tex`-ийг засна.

## Эх сурвалжийн зам

Анхдагчаар `..` (сангийн үндэс) фолдероос уншина. Өөр газар байвал:

```bash
make SRC=/зам/эх/сан
# эсвэл
python3 build.py --src /зам/эх/сан --pdf
```

## `build.py` юу хийдэг вэ

| Алхам | Тайлбар |
|---|---|
| Тэмдэгт солих | DejaVu-д байхгүй эможи (⭐, ⛔) → текст |
| `<details>` задлах | HTML нугалах блокийг энгийн догол мөр болгоно |
| H1 гарчиг таслах | Файлын эхний `#` гарчгийг бүлгийн нэр болгоно |
| Бөглөх зурвас | `______` → `\rule` (кодын блокоос ГАДНА л) |
| Үүрлэсэн блок | ` ```` ` доторх ` ```mermaid ` -ийг задлана |
| pandoc дуудах | Markdown → LaTeX, tango өнгөлөлттэй |
| Хүснэгт жижигрүүлэх | `longtable` бүрийг `\scriptsize` болгоно |
| Урт танигч таслах | `\texttt{A__B__C}` дотор мөр таслахыг зөвшөөрнө |

## Чанарын шалгалт

```bash
make check
```

Одоогийн байдал: **дутуу тэмдэгт 0**, хүрээнээс хэтэрсэн мөр 6 (бүгд 26pt-ээс
бага, хүснэгт доторх урт танигчаас үүдэлтэй).

## Загварыг өөрчлөх

`preamble.tex` дотор:

| Юу | Хаана |
|---|---|
| Фонт | `\setmainfont`, `\setsansfont`, `\setmonofont` |
| Өнгө | `\definecolor{cncblue}` гэх мэт |
| Хуудасны хэмжээ | `\usepackage[...]{geometry}` |
| Гарчгийн загвар | `\titleformat{\chapter}` |
| Тэмдэглэлийн хайрцаг | `\newtcolorbox{cncnote}` |
| Кодын блокийн хэмжээ | `\AtBeginDocument{...fontsize=\scriptsize}` |

Гарчгийн хуудасны мэдээлэл (багшийн нэр, тэнхим, хувилбар) `main.tex`-ийн
эхэнд `\newcommand`-оор тодорхойлогдсон.

## Хэвлэх

Гарын авлага **A4, нэг талд** (`oneside`) зохиогдсон. Хоёр талд хэвлэх бол
`main.tex`-ийн эхний мөрийг:

```latex
\documentclass[11pt,a4paper,twoside,openright]{report}
```

болгож, `preamble.tex`-ийн `geometry`-д `bindingoffset=6mm` нэмнэ.
