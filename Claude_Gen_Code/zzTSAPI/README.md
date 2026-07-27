# zzStructure POC API (TypeScript)

A TypeScript/Node.js implementation of the proof-of-concept REST API
described in `zzstructure-poc-spec.md`: two independent zzStructures
("Alice" and "Bob"), each persisted as a JSON file, exposing a REST API for
managing cells/dimensions/connections and weaving cells discovered in each
other's structures into their own.

This is a POC: single Node process, localhost only, no TLS, two hardcoded
users, bearer-UUID "auth."

## 1. Prerequisites

- **Node.js 18+** (developed/tested on Node 22). Check with `node --version`.
- **npm** (ships with Node).
- **curl** and **python3** — only needed to run `scripts/run-tests.sh`; the
  server itself has no Python dependency. (The test script uses `python3`
  instead of `jq` so you don't need to install anything extra.)

## 2. Project layout

```
zzstructure-poc/
  data/
    authorization.json   # fixed: Alice's and Bob's UUIDs, checked into the repo
    alice.json            # generated on first run — gitignored
    bob.json               # generated on first run — gitignored
  src/
    types.ts                # shared vocabulary (Cell/Dimension/Connection/Snapshot, error codes)
    engine.ts                 # pure domain engine (link/unlink, bootstrap, addDimension, etc.)
    persistence.ts             # the only module that touches the filesystem
    auth.ts                     # bearer-token resolution against authorization.json
    store.ts                     # in-memory Map<userId, snapshot>, per-user mutex, revision bookkeeping
    routes/structures.ts          # the 10 HTTP endpoints from spec §7
    server.ts                      # Express wiring / entry point
  scripts/
    run-tests.sh                    # exercises the spec's §9 test plan end-to-end
  package.json
  tsconfig.json
```

## 3. Setup

From the project root:

```bash
npm install
```

This installs `express` and `uuid` (runtime) plus `typescript`, `tsx`, and
type definitions (dev).

## 4. Running the server

### Option A — compiled (recommended for testing)

```bash
npm run build      # compiles src/ -> dist/ via tsc
npm start          # runs node dist/server.js
```

### Option B — dev mode (auto-restart on file changes, no separate build step)

```bash
npm run dev        # runs src/server.ts directly via tsx
```

Either way, you should see:

```
zzStructure POC API listening on http://localhost:3000
Data directory: /path/to/zzstructure-poc/data
  Alice: 11111111-1111-7111-8111-111111111111 -> alice.json
  Bob: 22222222-2222-7222-8222-222222222222 -> bob.json
```

On this first run, `data/alice.json` and `data/bob.json` don't exist yet, so
the server bootstraps both (seven system dimensions, the `d.dimensions`
ring, the `d` namespace head, H-view/I-view registration — spec §5) and
writes the files immediately, before accepting any requests. This is eager
bootstrap at startup, per spec §3.4, so the files are inspectable right
away:

```bash
cat data/alice.json | python3 -m json.tool | head -30
```

**Environment variables** (both optional):

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `3000` | HTTP port |
| `ZZ_DATA_DIR` | `<project root>/data` | Where `authorization.json`/`alice.json`/`bob.json` live |

```bash
PORT=4000 npm start
```

## 5. Resetting to a clean bootstrap state

To wipe Alice's and Bob's structures and start fresh on the next server
start:

```bash
npm run reset-data      # deletes data/alice.json and data/bob.json
```

(`data/authorization.json` is checked in and never touched by the app — it
defines the two fixed user UUIDs the test script and the examples below
rely on.)

## 6. Running the automated test suite

The test script exercises the walkthrough in spec §9 (TC-01 through TC-27,
adapted to work with runtime-generated UUIDs instead of literal ones) as a
sequential integration run against a live server.

**Step 1 — reset data and start the server in one terminal:**

```bash
npm run build
npm run reset-data
npm start
```

Leave this running. Wait for the "listening on http://localhost:3000" line.

**Step 2 — in a second terminal, run the tests:**

```bash
npm test
# or directly:
./scripts/run-tests.sh
```

If your server is on a non-default port or host, pass the base URL as an
argument:

```bash
./scripts/run-tests.sh http://localhost:4000
```

Expected output ends with:

```
-----------------------------------
Passed: 29   Failed: 0
-----------------------------------
```

The script exits `0` on full success and `1` if any assertion fails, so it
can be wired into CI. Each test prints `PASS`/`FAIL` with the expected vs.
actual status code and body on failure.

**Note:** the test script mutates Alice's and Bob's structures as it runs
(creating documents, dimensions, links — mirroring §9's fixtures). Re-run
`npm run reset-data` and restart the server before re-running the script if
you want a clean slate; running it twice against the same server without
resetting will hit `409 duplicate_dimension` on the second run's dimension
creation.

## 7. Trying it manually with curl

The two user UUIDs are fixed in `data/authorization.json`:

```bash
ALICE=11111111-1111-7111-8111-111111111111
BOB=22222222-2222-7222-8222-222222222222
```

**Read Alice's system dimensions:**

```bash
curl -s http://localhost:3000/structures/$ALICE/dimensions \
  -H "Authorization: Bearer $ALICE" | python3 -m json.tool
```

**Alice creates a document cell:**

```bash
curl -s -X POST http://localhost:3000/structures/$ALICE/documents \
  -H "Authorization: Bearer $ALICE" \
  -H "Content-Type: application/json" \
  -d '{"documentId":"alice/2024-01-01-morning-pages.md"}'
# -> {"cellId":"...","created":true,"revision":1}
```

**Bob tries to write into Alice's structure (should fail with 403):**

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:3000/structures/$ALICE/documents \
  -H "Authorization: Bearer $BOB" \
  -H "Content-Type: application/json" \
  -d '{"documentId":"anything"}'
# -> 403
```

**Missing auth header (should fail with 401):**

```bash
curl -s http://localhost:3000/structures/$ALICE/dimensions
# -> {"error":"unauthorized"}
```

See spec §7 for the full request/response shape of all ten endpoints.

## 8. Implementation notes / deviations from the illustrative spec examples

The spec is precise about behavior (Restriction R, single-writer, mirrored
connections, revision semantics, bootstrap producing 12 cells / 7
dimensions) but the exact internal wiring of a couple of pieces is only
sketched, since it's a direct port of engine code not included in the spec
document. Where the spec's example fixtures show elided detail (e.g. §9.2's
`connections` array), this implementation makes the following concrete
choices, all internally consistent and covered by the test script:

- **d.dimensions ring insertion**: new dimensions are spliced in immediately
  before the ring closes back on the `d.dimensions` anchor cell (i.e.
  appended at the end of the ring, just before the wrap-around edge).
- **Namespace filing**: the first dimension in a namespace creates that
  namespace's head cell and links it to the new dimension cell via
  `d.namespace-members`; every subsequent dimension in the same namespace is
  appended to the end of the existing chain via `d.namespace-siblings`.
- **Clones**: `d.clones` links form a chain off the original cell (so a cell
  can be cloned more than once without hitting a Restriction R violation on
  the second clone).
- **Grid layout (`GET /view`)**: implemented as a breadth-first walk from
  the `accursed` cell along the requested `x`/`y`(/`z`) dimensions,
  assigning integer coordinates per hop. This satisfies the placement shape
  in spec §7.1 and the cross-user visibility test in §9 (TC-19/TC-20). It
  does not implement a full virtual-copy model for cells reachable by
  multiple paths through a cyclic layout — the `isVirtualCopy` field is
  present in every response but always `false` in this POC.
- **UUIDs**: generated ids use UUIDv7 (time-ordered), matching spec §5's
  mention of "the UUIDv7 scheme." The seven system dimension ids and their
  dimension-cell ids are the literal fixed values from spec §9.1, identical
  across both files.

None of these choices affect the documented API surface (request/response
shapes, status codes, error codes) — they only affect the internal
`connections` bookkeeping that isn't part of any response body except
`GET /structures/{id}/export`.

## 9. Troubleshooting

- **`Error: listen EADDRINUSE`** — something else is already on port 3000.
  Either stop it or run with `PORT=4000 npm start` (and pass the matching
  URL to the test script).
- **Test script reports failures on a second run** — you likely didn't
  reset data between runs; see §6.
- **`data/alice.json` looks corrupted or truncated** — delete it (and
  `bob.json`) and restart the server; it will re-bootstrap from scratch.
