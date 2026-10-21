Claude generated python script for producing a markdown file from a comment thread for a document on Seed Hypermedia.

```
First extract the comment thread to a text file:
seed-cli comment list https://hyper.media/hm/z6MksUtEc1kUMN3nazJWpRuVDZ7mYoy4Qi3JHLDB5B7x2oLA/feedback-for-seed-team/2026-10-20-initial-comments > feedback.txt 

Then run the python script:

python3 comments_to_md.py feedback.txt
feedback.txt -> feedback.md
```
