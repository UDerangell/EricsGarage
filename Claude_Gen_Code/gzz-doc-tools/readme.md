Scripts for extracting text from legacy Gzz documentation files

WML conversion:
```
usage: wml2txt.py INPUT.wml [OUTPUT.txt]
```
LaTeX conversion:
```
usage: tex2txt.py INPUT.tex [OUTPUT.txt]
```
Sample run:
```
ericrangell@Erics-MacBook-Air Gentle_Introduction % ls
Makefile	README		gi.wml		zzgentle.tex
ericrangell@Erics-MacBook-Air Gentle_Introduction % python3 ../tex2txt.py zzgentle.tex
coverage: 7634 words out / 7854 words in (97%)
zzgentle.tex -> zzgentle.txt
ericrangell@Erics-MacBook-Air Gentle_Introduction % python3 ../wml2txt.py gi.wml
coverage: 3534 words out / 3514 words in (101%)
gi.wml -> gi.txt: 88 blocks
```
The 2 output txt files are included in this repository as samples.

To convert Diagram (DIA) files to PNG:
```
python3 -m venv venv
  source venv/bin/activate        # Windows: venv\Scripts\activate
  pip install pillow
  python dia2png.py yourfile.dia
```
