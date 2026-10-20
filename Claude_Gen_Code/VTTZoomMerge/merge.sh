ls *.vtt > vttfile.in
ls *.txt > txtfile.in
vttfile=$(cat vttfile.in)
txtfile=$(cat txtfile.in)
outfile="${vttfile// /_}.md"
python3 vtt_to_transcript.py "$vttfile" -o "$outfile" --chat "$txtfile" --meeting-start "2026-09-07 11:30:00"
