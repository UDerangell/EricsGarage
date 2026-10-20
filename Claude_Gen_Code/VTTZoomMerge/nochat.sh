ls *.vtt > vttfile.in
ls *.txt > txtfile.in
vttfile=$(cat vttfile.in)
txtfile=$(cat txtfile.in)
outfile="${vttfile// /_}.md"
#python3 merge_transcript_chat.py "$vttfile" "$txtfile" "$outfile"
python3 vtt_to_transcript.py "$vttfile" -o "$outfile"
