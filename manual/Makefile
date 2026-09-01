# CNC302 — Лабораторийн гарын авлага (LaTeX)
#
#   make          — Markdown-оос .tex үүсгээд PDF болгоно
#   make tex      — зөвхөн chapters/*.tex шинэчилнэ
#   make pdf      — байгаа .tex-ээс PDF хийнэ
#   make watch    — өөрчлөлт бүрт дахин хөрвүүлнэ (latexmk)
#   make clean    — түр файлуудыг устгана
#   make distclean— PDF-ийг ч устгана

SRC      ?= ..
MAIN      = main
ENGINE    = xelatex
TEXFLAGS  = -interaction=nonstopmode -halt-on-error

.PHONY: all tex pdf watch clean distclean check

all: tex pdf

tex:
	@python3 build.py --src $(SRC)

pdf:
	@echo "→ $(ENGINE) ×3 …"
	@$(ENGINE) $(TEXFLAGS) $(MAIN).tex > /dev/null
	@$(ENGINE) $(TEXFLAGS) $(MAIN).tex > /dev/null
	@$(ENGINE) $(TEXFLAGS) $(MAIN).tex | tail -3
	@echo "✓ $(MAIN).pdf"

watch:
	latexmk -pdfxe -pvc $(MAIN).tex

# Хөрвүүлэлтийн чанарыг шалгах
check:
	@echo "── Дутуу тэмдэгт ──"
	@grep -c "Missing character" $(MAIN).log || echo 0
	@echo "── Хүрээнээс хэтэрсэн мөр ──"
	@grep -c "Overfull .hbox" $(MAIN).log || echo 0
	@echo "── Хуудасны тоо ──"
	@grep -o "Output written on $(MAIN).pdf ([0-9]* pages" $(MAIN).log | grep -o "[0-9]*" | head -1

clean:
	@rm -f *.aux *.log *.out *.toc *.lof *.lot *.fls *.fdb_latexmk \
	       *.synctex.gz *.bbl *.blg *.idx *.ilg *.ind chapters/*.aux
	@echo "✓ цэвэрлэв"

distclean: clean
	@rm -f $(MAIN).pdf p-*.jpg
