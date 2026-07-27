This is the generated code for v0.01 of the Typescript API for zzStructure

Sample Run:

zzStructure POC API listening on http://localhost:3000
Data directory: /Users/ericrangell/git/zzTSAPI/data
  Alice: 11111111-1111-7111-8111-111111111111 -> alice.json
  Bob: 22222222-2222-7222-8222-222222222222 -> bob.json

% ./run-tests.sh

Auth
  PASS TC-01 missing auth header -> 401
  PASS TC-02 unknown bearer uuid -> 401

Bootstrap sanity
  PASS TC-03 Alice has 7 system dimensions after bootstrap
  PASS Bob has 7 system dimensions after bootstrap

Cross-user reads
  PASS TC-04 Alice reads Bob's dimensions (status 200)
  PASS TC-27 unknown structure id -> 404

Alice: documents, dimensions, links, Restriction R
  PASS TC-05 Alice creates her first document cell (revision=1)
  PASS TC-06 Alice creates dimension user.journal
  PASS TC-07 Alice creates a second document cell (status 200)
  PASS TC-08 Alice links her two entries along user.journal (status 200)
  PASS TC-09 duplicate dimension name rejected -> 409
  PASS TC-10 self-link forbidden -> 400
  PASS TC-11 Restriction R violation -> 409

Bob: documents, dimensions, single-writer enforcement
  PASS TC-12 Bob creates his document cell (status 200)
  PASS TC-13 Bob creates his own dimension (status 200)
  PASS TC-14 cross-user write forbidden -> 403

Cross-user linking and view isolation
  PASS TC-15 Bob reads one of Alice's cells
  PASS TC-16 Bob imports Alice's cell into his own cache
  PASS TC-17 Bob creates a dimension to relate to it (status 200)
  PASS TC-18 Bob links his cell to Alice's imported cell (status 200)
  PASS TC-18b alice.json byte-for-byte unchanged by Bob's link
  PASS TC-19 Bob's view includes Alice's imported cell, tagged foreign
  PASS TC-20 Alice's own view is unaffected by Bob's link

Unlink
  PASS TC-21 Bob unlinks the cross-user edge (status 200)
  PASS TC-22 unlinking a non-existent edge -> 404

Clone, export, optimistic concurrency
  PASS TC-23 Alice clones a cell (status 200)
  PASS TC-24 export matches the file on disk (revision 6)
  PASS TC-25 optimistic concurrency conflict -> 409
  PASS TC-26 importing a non-existent foreign cell -> 404

-----------------------------------
Passed: 29   Failed: 0
-----------------------------------

