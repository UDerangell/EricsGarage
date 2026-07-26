# zzStructure REST API — Proof of Concept Specification

## 1. Overview

This document specifies a proof-of-concept Node.js application that exposes a
REST API for two independent zzStructures — one owned by Alice, one owned by
Bob — each persisted as a plain JSON file on the local filesystem. The API
lets each user manage their own structure (cells, dimensions, connections)
and read cell/connection data from the other user's structure, so that Alice
and Bob can weave cells they discover in each other's structures into their
own, using dimensions they each control.

This is a proof of concept: single Node process, localhost only, no TLS, no
real identity provider, two hardcoded users. The goal is to validate the
architecture and message shapes discussed in prior design work, not to ship
a production multi-tenant service.

## 2. Goals and non-goals

**In scope**

- A REST API, running on `http://localhost:PORT`, backed by two JSON files
  (`alice.json`, `bob.json`) plus one authorization file
  (`authorization.json`).
- Bootstrapping each user's file with the standard zzStructure system
  scaffolding (the seven system dimensions, the `d.dimensions` ring, the `d`
  namespace, and the H-view/I-view registration) the first time that file is
  needed.
- UUID-based caller identification, validated against the authorization
  file, with single-writer enforcement (a caller may only mutate the
  structure whose id matches their own).
- Cross-user reads: either user may read the other's cells, dimensions, and
  rendered views.
- Cross-user linking: either user may copy a read-only reference to the
  other's cell into their own structure and link it along a dimension they
  own, without mutating the other user's file.

**Out of scope**

- Real authentication (OAuth, sessions, passwords). A bearer UUID is treated
  as sufficient proof of identity for this POC.
- Fine-grained read permissions (visibility settings, allow-lists). Both
  seeded users can read each other unconditionally.
- More than two users. The authorization file format supports more, but
  this spec's test plan only exercises Alice and Bob.
- Networked/decentralized storage, paragraph-level addressing, or any of the
  docuverse extensions discussed separately — this POC's documents are
  opaque string IDs, exactly as in the existing desktop engine.
- A UI. This is API-only; a test script (or curl/Postman collection) is the
  intended client.

## 3. Architecture

```
/poc
  /data
    authorization.json      # who is allowed to call the API
    alice.json               # Alice's zzStructure snapshot
    bob.json                 # Bob's zzStructure snapshot
  /src
    server.js                 # HTTP entry point, route wiring
    auth.js                    # bearer-UUID lookup against authorization.json
    persistence.js             # load(userId) / save(userId, snapshot)
    engine.js                   # cells, dimensions, connections, link/unlink,
                                  #   rank, bootstrap, view layout (HView/IView)
    routes/
      structures.js
```

Three layers, matching the ports-and-adapters split from the wider API
design:

1. **HTTP layer** (`server.js`, `routes/`) — parses requests, resolves the
   caller's identity via `auth.js`, enforces single-writer on mutating
   routes, and serializes engine output back to JSON.
2. **Domain engine** (`engine.js`) — a direct port of the existing
   `ZZStructure` logic: the cell/dimension/connection tables, Restriction R,
   `link`/`unlink`, `rank(through:along:)`, `makeClone`, `addDimension`,
   `bootstrap`, and the `gridLayout` algorithm behind H-view/I-view. It knows
   nothing about HTTP or file paths.
3. **Persistence adapter** (`persistence.js`) — the only code that touches
   the filesystem. Exposes exactly two operations, matching the pluggable
   port from the wider design:

   ```js
   load(userId)          // -> Snapshot | null
   save(userId, snapshot) // -> void, atomic write
   ```

   For this POC the adapter is hardcoded to read/write
   `data/alice.json`/`data/bob.json` via a static `userId -> filename` map
   taken from `authorization.json` (see §4.2). Swapping in a different
   backend later means replacing this file only.

**Process model.** One Node process holds both structures in memory as
`Map<userId, { snapshot, mutex }>`, loaded lazily on first request (running
`bootstrap()` if no file exists) or eagerly at startup — either is
acceptable for the POC; the test plan in §9 assumes eager bootstrap at
startup so file contents are inspectable immediately. Every mutating
request for a given `userId` acquires that user's mutex before touching the
in-memory snapshot, mutates it, writes it to disk, then releases — this is
the Node equivalent of the existing engine's `@MainActor` serialization, just
scoped per user instead of per process.

## 4. Data model

### 4.1 Cell

```json
{
  "id": "3ab21b4e-6f2a-7c31-9a10-0c1145ac0011",
  "kind": "document",
  "documentId": "alice/2024-01-01-morning-pages.md",
  "ownerId": "11111111-1111-7111-8111-111111111111"
}
```

`kind` is a flat discriminator. The fields that accompany it depend on the
value:

| `kind` | additional fields |
|---|---|
| `document` | `documentId: string` |
| `dimension` | `dimensionId: uuid` |
| `view` | `viewId: string` |
| `namespaceHead` | `name: string` |
| `clone` | `of: uuid` (the head cell it clones) |
| `plain` | — |

`ownerId` is always the UUID of the structure that minted this cell. A cell
present in a structure's file with an `ownerId` other than that structure's
own `ownerId` is a **foreign cell cache entry** — a read-only copy imported
via `POST /foreign-cells` (§7.9).

### 4.2 Dimension

```json
{
  "id": "00000000-0000-7000-8000-00000000D001",
  "namespace": "d",
  "name": "dimensions",
  "qualifiedName": "d.dimensions",
  "dimensionCellId": "00000000-0000-7000-8000-00000000C001",
  "ownerId": "11111111-1111-7111-8111-111111111111"
}
```

Every dimension in a user's file is owned by that same user — a dimension
never appears in a structure it doesn't govern. (System dimensions share the
same fixed `id` across both files by convention, so the two structures stay
"the same shape," but the edges each dimension carries are private per
file — see §5.)

### 4.3 Connection

```json
{
  "cellId": "3ab21b4e-6f2a-7c31-9a10-0c1145ac0011",
  "dimensionId": "00000000-0000-7000-8000-00000000D001",
  "negwardId": null,
  "poswardId": "9e1f7a02-....-b2a0"
}
```

Stored twice per edge (once on each cell), mirrored by `link`/`unlink`,
exactly as in the desktop engine.

### 4.4 Snapshot (the on-disk file format)

```json
{
  "schemaVersion": 1,
  "ownerId": "11111111-1111-7111-8111-111111111111",
  "revision": 0,
  "cells": [ /* ZZCell[] */ ],
  "dimensions": [ /* ZZDimension[] */ ],
  "connections": [ /* ZZConnection[] */ ]
}
```

`revision` increments by exactly 1 on every successful mutating call against
that file. It is returned in every response and accepted as an optional
`expectedRevision` on mutating requests for optimistic concurrency (§7.4,
§9 TC-25).

### 4.5 Authorization file

```json
{
  "users": [
    {
      "id": "11111111-1111-7111-8111-111111111111",
      "displayName": "Alice",
      "handle": "alice",
      "dataFile": "alice.json"
    },
    {
      "id": "22222222-2222-7222-8222-222222222222",
      "displayName": "Bob",
      "handle": "bob",
      "dataFile": "bob.json"
    }
  ]
}
```

`auth.js` loads this file once at startup. A request's bearer token is
looked up against `users[].id`; no match means the caller is unauthenticated
regardless of what `structureId` they're asking about.

## 5. Bootstrap behavior

On startup, for each user listed in `authorization.json`, the server checks
whether `data/<dataFile>` exists.

- **If it exists**: load it, verify/repair connection mirrors (same
  invariant check as `loadOrBootstrap`), and keep it in memory.
- **If it does not exist**: create a fresh `Snapshot` with
  `ownerId = user.id`, `revision = 0`, run `bootstrap()` against it (below),
  then `save()` it immediately so the file exists on disk before the first
  request can arrive.

`bootstrap()` is a direct port of the existing engine's routine:

1. Register the seven system dimensions and their cells (fixed UUIDs,
   identical across every install — see the table in §9.1).
2. Thread `d.dimensions` into a self-including ring containing all seven.
3. File all seven system dimensions under a `d`-namespace head cell
   (created fresh — its own id is generated at bootstrap time and will
   differ between Alice's and Bob's files, since each user's namespace tree
   is private).
4. Register `HView` and `IView` on `d.views`, and clone each onto
   `d.user-views` (enabled-by-default).

Nothing user-specific is seeded — no example documents, no example
dimensions. Alice's and Bob's files are byte-for-byte identical in
structure immediately after bootstrap, differing only in `ownerId` and the
randomly generated ids for the namespace head, the two view cells' clones,
and (per the UUIDv7 scheme) the low bits of every generated id. The test
plan in §9 has Alice and Bob build their own content from there via the
API, exactly as they would in the real app.

## 6. Authentication and authorization model

Every request must carry:

```
Authorization: Bearer <uuid>
```

Resolution, in order:

1. **No header, malformed header, or UUID not present in
   `authorization.json`** → `401 unauthorized`. No further checks run.
2. **Path references a `structureId` not present in `authorization.json`**
   → `404 unknown_structure`, even for an authenticated caller.
3. **Mutating routes** (`POST`/`DELETE`) additionally require
   `callerId === structureId` → otherwise `403 forbidden`. This is the
   single-writer rule: Bob can never write into `alice.json`, and vice
   versa, regardless of what the request body contains.
4. **Read routes** (`GET`) have no additional check in this POC — any
   authenticated user may read any known structure. This is a deliberate
   simplification (see §2); a production version would consult a
   visibility policy here.

## 7. API reference

Base URL: `http://localhost:PORT`. All bodies and responses are JSON.
`{structureId}` is always a user's UUID.

| # | Method | Path | Auth | Engine call |
|---|---|---|---|---|
| 1 | GET | `/structures/{id}/view` | any known caller | `gridLayout` via `HView`/`IView` |
| 2 | GET | `/structures/{id}/cells/{cellId}` | any known caller | cell lookup + `dimensions(at:)` |
| 3 | GET | `/structures/{id}/dimensions` | any known caller | `allDimensions()` |
| 4 | POST | `/structures/{id}/links` | caller === id | `link(a, poswardTo: b, along: d, ...)` |
| 5 | DELETE | `/structures/{id}/links` | caller === id | `unlink(a, poswardFrom: b, along: d)` |
| 6 | POST | `/structures/{id}/dimensions` | caller === id | `addDimension(name, namespace)` |
| 7 | POST | `/structures/{id}/clones` | caller === id | `makeClone(of:)` |
| 8 | POST | `/structures/{id}/documents` | caller === id | `cell(forDocument:)` |
| 9 | POST | `/structures/{id}/foreign-cells` | caller === id | import a cached cell from another structure |
| 10 | GET | `/structures/{id}/export` | any known caller | full `Snapshot` |

### 7.1 `GET /structures/{id}/view`

Query params: `accursed` (cell id), `view` (`h-view` \| `i-view`), `x`, `y`
(dimension ids), `z` (optional dimension id).

```json
// 200
{
  "revision": 4,
  "view": "h-view",
  "axes": { "x": "<dim>", "y": "<dim>", "z": null },
  "accursed": "<cellId>",
  "placedCells": [
    { "cellId": "<cellId>", "x": 0, "y": 0, "z": 0, "isVirtualCopy": false }
  ],
  "cells": { "<cellId>": { "kind": "document", "documentId": "...", "ownerId": "<uuid>" } },
  "dimensions": { "<dimId>": { "namespace": "d", "name": "dimensions", "qualifiedName": "d.dimensions" } }
}
```

### 7.2 `GET /structures/{id}/cells/{cellId}`

```json
// 200
{ "cell": { "id": "<cellId>", "kind": "document", "documentId": "...", "ownerId": "<uuid>" },
  "dimensionsPresent": [ { "id": "<dimId>", "qualifiedName": "user.journal", "ownerId": "<uuid>" } ] }
```

`404 unknown_cell` if absent from that structure.

### 7.3 `GET /structures/{id}/dimensions`

```json
// 200
{ "dimensions": [ { "id": "...", "namespace": "d", "name": "dimensions", "qualifiedName": "d.dimensions", "ownerId": "<uuid>" } ] }
```

### 7.4 `POST /structures/{id}/links`

```json
// request
{ "a": "<cellId>", "b": "<cellId>", "dimension": "<dimId>",
  "splice": false, "allowSelfRing": false, "expectedRevision": 4 }
```

```json
// 200
{ "revision": 5 }
```

Errors: `400 self_link_forbidden`, `404 unknown_cell` / `unknown_dimension`,
`409 restriction_r_violation`, `409 revision_conflict` (only if
`expectedRevision` was supplied and didn't match).

### 7.5 `DELETE /structures/{id}/links`

```json
// request
{ "a": "<negwardCellId>", "b": "<poswardCellId>", "dimension": "<dimId>" }
```

```json
// 200
{ "revision": 6 }
```

`404 no_such_connection` if `a`→`b` isn't currently linked along that
dimension.

### 7.6 `POST /structures/{id}/dimensions`

```json
// request
{ "name": "journal", "namespace": "user" }
```

```json
// 200
{ "dimension": { "id": "<newDimId>", "namespace": "user", "name": "journal",
                  "qualifiedName": "user.journal", "dimensionCellId": "<newCellId>",
                  "ownerId": "<uuid>" },
  "revision": 2 }
```

`409 duplicate_dimension` if `namespace.name` already exists in this
structure.

### 7.7 `POST /structures/{id}/clones`

```json
// request
{ "of": "<cellId>" }
```

```json
// 200
{ "cloneCellId": "<newCloneId>", "revision": 7 }
```

`404 unknown_cell` if `of` is absent.

### 7.8 `POST /structures/{id}/documents`

```json
// request
{ "documentId": "alice/2024-01-01-morning-pages.md" }
```

```json
// 200
{ "cellId": "<cellId>", "created": true, "revision": 1 }
```

`created: false` and the existing `cellId` if that `documentId` already has
a cell (find-or-create semantics).

### 7.9 `POST /structures/{id}/foreign-cells`

```json
// request
{ "foreignCellId": "<alice's cell id>", "ownerId": "<alice's userId>" }
```

The server reads `foreignCellId` out of `ownerId`'s **own** in-memory
snapshot (an internal read, not a second HTTP hop, since both structures
live in the same process for this POC) and copies its `kind` fields into a
new cell entry in the caller's own file, tagged with the true `ownerId`.

```json
// 200
{ "cell": { "id": "<alice's cell id>", "kind": "document",
            "documentId": "alice/2024-01-01-morning-pages.md",
            "ownerId": "<alice's userId>" },
  "revision": 3 }
```

`404 foreign_cell_not_found` if `foreignCellId` doesn't exist in
`ownerId`'s structure. `404 unknown_structure` if `ownerId` isn't a known
user.

### 7.10 `GET /structures/{id}/export`

```json
// 200 — the Snapshot exactly as stored on disk
{ "schemaVersion": 1, "ownerId": "<uuid>", "revision": 7,
  "cells": [...], "dimensions": [...], "connections": [...] }
```

## 8. Error model

```json
{ "error": "restriction_r_violation", "message": "posward of the first cell is already occupied" }
```

| HTTP | `error` | Cause |
|---|---|---|
| 400 | `self_link_forbidden` | `a === b` without `allowSelfRing` |
| 400 | `validation_error` | missing/malformed request fields |
| 401 | `unauthorized` | missing, malformed, or unrecognized bearer token |
| 403 | `forbidden` | mutating a structure the caller doesn't own |
| 404 | `unknown_structure` | `{id}` not in the authorization file |
| 404 | `unknown_cell` | referenced cell id not present in the target structure |
| 404 | `unknown_dimension` | referenced dimension id not present in the target structure |
| 404 | `no_such_connection` | `DELETE /links` found no matching edge |
| 404 | `foreign_cell_not_found` | `foreignCellId` absent from the named owner's structure |
| 409 | `duplicate_dimension` | `namespace.name` already exists in this structure |
| 409 | `restriction_r_violation` | a required posward/negward slot is already occupied |
| 409 | `revision_conflict` | `expectedRevision` didn't match the structure's current revision |

## 9. Test plan

### 9.1 Fixtures

Symbolic ids used throughout this section (actual values are generated
UUIDv7s at runtime; the system dimension ids below are the only ones fixed
by the engine itself and will be literal in every install):

| Symbol | Meaning |
|---|---|
| `ALICE` | `11111111-1111-7111-8111-111111111111` |
| `BOB` | `22222222-2222-7222-8222-222222222222` |
| `D.DIMENSIONS` | `00000000-0000-7000-8000-00000000D001` |
| `D.NAMESPACES` | `00000000-0000-7000-8000-00000000D002` |
| `D.NS-MEMBERS` | `00000000-0000-7000-8000-00000000D003` |
| `D.NS-SIBLINGS` | `00000000-0000-7000-8000-00000000D004` |
| `D.VIEWS` | `00000000-0000-7000-8000-00000000D005` |
| `D.CLONES` | `00000000-0000-7000-8000-00000000D006` |
| `D.USER-VIEWS` | `00000000-0000-7000-8000-00000000D007` |
| `<a-doc-A>`, `<a-doc-B>` | Alice's two document cells, created in TC-05/TC-07 |
| `<a-dim-journal>` | Alice's `user.journal` dimension, created in TC-06 |
| `<b-doc-C>` | Bob's document cell, created in TC-12 |
| `<b-dim-related>` | Bob's `user.related-reading` dimension, created in TC-17 |

Tests run in order against a single shared fixture (the two freshly
bootstrapped files) — this is an integration sequence, not independent unit
tests, because the interaction pattern between Alice and Bob is the thing
under test.

### 9.2 TC-00 — Bootstrap on first run

**Setup**: delete `data/alice.json` and `data/bob.json` if present, start
the server.

**Expected**: both files are created. `alice.json` (Bob's is structurally
identical with `ownerId` swapped and different generated ids):

```json
{
  "schemaVersion": 1,
  "ownerId": "11111111-1111-7111-8111-111111111111",
  "revision": 0,
  "cells": [
    { "id": "00000000-0000-7000-8000-00000000C001", "kind": "dimension", "dimensionId": "00000000-0000-7000-8000-00000000D001", "ownerId": "ALICE" },
    { "id": "00000000-0000-7000-8000-00000000C002", "kind": "dimension", "dimensionId": "00000000-0000-7000-8000-00000000D002", "ownerId": "ALICE" },
    { "id": "00000000-0000-7000-8000-00000000C003", "kind": "dimension", "dimensionId": "00000000-0000-7000-8000-00000000D003", "ownerId": "ALICE" },
    { "id": "00000000-0000-7000-8000-00000000C004", "kind": "dimension", "dimensionId": "00000000-0000-7000-8000-00000000D004", "ownerId": "ALICE" },
    { "id": "00000000-0000-7000-8000-00000000C005", "kind": "dimension", "dimensionId": "00000000-0000-7000-8000-00000000D005", "ownerId": "ALICE" },
    { "id": "00000000-0000-7000-8000-00000000C006", "kind": "dimension", "dimensionId": "00000000-0000-7000-8000-00000000D006", "ownerId": "ALICE" },
    { "id": "00000000-0000-7000-8000-00000000C007", "kind": "dimension", "dimensionId": "00000000-0000-7000-8000-00000000D007", "ownerId": "ALICE" },
    { "id": "<ns-head-d>", "kind": "namespaceHead", "name": "d", "ownerId": "ALICE" },
    { "id": "<view-hview>", "kind": "view", "viewId": "h-view", "ownerId": "ALICE" },
    { "id": "<view-iview>", "kind": "view", "viewId": "i-view", "ownerId": "ALICE" },
    { "id": "<clone-hview>", "kind": "clone", "of": "<view-hview>", "ownerId": "ALICE" },
    { "id": "<clone-iview>", "kind": "clone", "of": "<view-iview>", "ownerId": "ALICE" }
  ],
  "dimensions": [
    { "id": "D.DIMENSIONS", "namespace": "d", "name": "dimensions", "qualifiedName": "d.dimensions", "dimensionCellId": "00000000-0000-7000-8000-00000000C001", "ownerId": "ALICE" },
    { "id": "D.NAMESPACES", "namespace": "d", "name": "namespaces", "qualifiedName": "d.namespaces", "dimensionCellId": "00000000-0000-7000-8000-00000000C002", "ownerId": "ALICE" },
    { "id": "D.NS-MEMBERS", "namespace": "d", "name": "namespace-members", "qualifiedName": "d.namespace-members", "dimensionCellId": "00000000-0000-7000-8000-00000000C003", "ownerId": "ALICE" },
    { "id": "D.NS-SIBLINGS", "namespace": "d", "name": "namespace-siblings", "qualifiedName": "d.namespace-siblings", "dimensionCellId": "00000000-0000-7000-8000-00000000C004", "ownerId": "ALICE" },
    { "id": "D.VIEWS", "namespace": "d", "name": "views", "qualifiedName": "d.views", "dimensionCellId": "00000000-0000-7000-8000-00000000C005", "ownerId": "ALICE" },
    { "id": "D.CLONES", "namespace": "d", "name": "clones", "qualifiedName": "d.clones", "dimensionCellId": "00000000-0000-7000-8000-00000000C006", "ownerId": "ALICE" },
    { "id": "D.USER-VIEWS", "namespace": "d", "name": "user-views", "qualifiedName": "d.user-views", "dimensionCellId": "00000000-0000-7000-8000-00000000C007", "ownerId": "ALICE" }
  ],
  "connections": [ /* the d.dimensions ring of all 7, the d namespace filing chain, the d.views/d.user-views chains — 20 records total */ ]
}
```

### 9.3 TC-01 — Missing auth header

**Request**: `GET /structures/ALICE/dimensions` with no `Authorization` header.
**Expected**: `401 { "error": "unauthorized" }`. `alice.json` unchanged.

### 9.4 TC-02 — Unknown UUID

**Request**: same, with `Authorization: Bearer 99999999-9999-7999-8999-999999999999`.
**Expected**: `401 { "error": "unauthorized" }`.

### 9.5 TC-03 — Read own dimensions

**Request**: `GET /structures/ALICE/dimensions`, bearer `ALICE`.
**Expected**: `200`, `dimensions` array of length 7, matching TC-00's list.

### 9.6 TC-04 — Cross-user read

**Request**: `GET /structures/BOB/view?accursed=<view-hview>&view=h-view&x=D.VIEWS&y=D.USER-VIEWS`, bearer `ALICE`.
**Expected**: `200`. Allowed — reads are open between known users in this POC. `bob.json` unchanged.

### 9.7 TC-05 — Alice creates her first document cell

**Request**: `POST /structures/ALICE/documents`, bearer `ALICE`,
body `{ "documentId": "alice/2024-01-01-morning-pages.md" }`.
**Expected**:
```json
{ "cellId": "<a-doc-A>", "created": true, "revision": 1 }
```
`alice.json`: `cells` gains one `{ "id": "<a-doc-A>", "kind": "document", "documentId": "alice/2024-01-01-morning-pages.md", "ownerId": "ALICE" }`; `revision` → 1.

### 9.8 TC-06 — Alice creates her own dimension

**Request**: `POST /structures/ALICE/dimensions`, bearer `ALICE`,
body `{ "name": "journal", "namespace": "user" }`.
**Expected**:
```json
{ "dimension": { "id": "<a-dim-journal>", "namespace": "user", "name": "journal",
                  "qualifiedName": "user.journal", "dimensionCellId": "<a-dim-journal-cell>",
                  "ownerId": "ALICE" },
  "revision": 2 }
```
`alice.json`: `dimensions` gains `user.journal`; `cells` gains its dimension
cell; `connections` gains one record extending Alice's `d.dimensions` ring
to include it, plus a fresh `user` namespace head cell and its filing
records under `d.namespace-members`/`d.namespace-siblings` (this is the
first `user`-namespace dimension Alice has created, so the head is created
now). `revision` → 2.

### 9.9 TC-07 — Alice creates a second document cell

**Request**: `POST /structures/ALICE/documents`, bearer `ALICE`,
body `{ "documentId": "alice/2024-01-08-morning-pages.md" }`.
**Expected**: `{ "cellId": "<a-doc-B>", "created": true, "revision": 3 }`.

### 9.10 TC-08 — Alice links her two entries along her own dimension

**Request**: `POST /structures/ALICE/links`, bearer `ALICE`,
body `{ "a": "<a-doc-A>", "b": "<a-doc-B>", "dimension": "<a-dim-journal>" }`.
**Expected**: `{ "revision": 4 }`. `alice.json` `connections` gains the mirrored pair: `<a-doc-A>` posward `<a-doc-B>`; `<a-doc-B>` negward `<a-doc-A>`, both keyed on `<a-dim-journal>`.

### 9.11 TC-09 — Duplicate dimension name rejected

**Request**: `POST /structures/ALICE/dimensions`, bearer `ALICE`,
body `{ "name": "journal", "namespace": "user" }`.
**Expected**: `409 { "error": "duplicate_dimension" }`. `alice.json` unchanged, `revision` stays 4.

### 9.12 TC-10 — Self-link forbidden

**Request**: `POST /structures/ALICE/links`, bearer `ALICE`,
body `{ "a": "<a-doc-A>", "b": "<a-doc-A>", "dimension": "<a-dim-journal>" }`.
**Expected**: `400 { "error": "self_link_forbidden" }`.

### 9.13 TC-11 — Restriction R violation

**Request**: Alice creates a third document `<a-doc-C>` (`POST /documents`,
revision → 5), then `POST /structures/ALICE/links`, bearer `ALICE`,
body `{ "a": "<a-doc-A>", "b": "<a-doc-C>", "dimension": "<a-dim-journal>" }`
(no `splice`), while `<a-doc-A>`'s posward slot along that dimension is
already occupied by `<a-doc-B>` from TC-08.
**Expected**: `409 { "error": "restriction_r_violation", "message": "posward of the first cell is already occupied" }`. `revision` stays 5.

### 9.14 TC-12 — Bob creates his document cell

**Request**: `POST /structures/BOB/documents`, bearer `BOB`,
body `{ "documentId": "bob/reading-list.md" }`.
**Expected**: `{ "cellId": "<b-doc-C>", "created": true, "revision": 1 }`.

### 9.15 TC-13 — Bob creates his own dimension

**Request**: `POST /structures/BOB/dimensions`, bearer `BOB`,
body `{ "name": "notes", "namespace": "user" }`.
**Expected**: `{ "dimension": {...qualifiedName: "user.notes"...}, "revision": 2 }`.

### 9.16 TC-14 — Cross-user write forbidden

**Request**: `POST /structures/ALICE/links`, bearer `BOB`,
body `{ "a": "<a-doc-A>", "b": "<a-doc-B>", "dimension": "<a-dim-journal>" }`.
**Expected**: `403 { "error": "forbidden" }`. `alice.json` unchanged. This is
the single-writer boundary — Bob's token is valid, but the target structure
isn't his.

### 9.17 TC-15 — Bob reads one of Alice's cells

**Request**: `GET /structures/ALICE/cells/<a-doc-A>`, bearer `BOB`.
**Expected**: `200`,
```json
{ "cell": { "id": "<a-doc-A>", "kind": "document", "documentId": "alice/2024-01-01-morning-pages.md", "ownerId": "ALICE" },
  "dimensionsPresent": [ { "id": "<a-dim-journal>", "qualifiedName": "user.journal", "ownerId": "ALICE" } ] }
```

### 9.18 TC-16 — Bob imports Alice's cell into his own cache

**Request**: `POST /structures/BOB/foreign-cells`, bearer `BOB`,
body `{ "foreignCellId": "<a-doc-A>", "ownerId": "ALICE" }`.
**Expected**:
```json
{ "cell": { "id": "<a-doc-A>", "kind": "document",
            "documentId": "alice/2024-01-01-morning-pages.md", "ownerId": "ALICE" },
  "revision": 3 }
```
`bob.json`: `cells` gains an entry for `<a-doc-A>` with `ownerId: "ALICE"`.
**`alice.json` is byte-for-byte unchanged** — this is the key assertion of
this test: importing is a read of Alice's structure and a write only to
Bob's.

### 9.19 TC-17 — Bob creates a dimension to relate to it

**Request**: `POST /structures/BOB/dimensions`, bearer `BOB`,
body `{ "name": "related-reading", "namespace": "user" }`.
**Expected**: `{ "dimension": {...qualifiedName: "user.related-reading"...}, "revision": 4 }`.

### 9.20 TC-18 — Bob links his cell to Alice's imported cell

**Request**: `POST /structures/BOB/links`, bearer `BOB`,
body `{ "a": "<b-doc-C>", "b": "<a-doc-A>", "dimension": "<b-dim-related>" }`.
**Expected**: `{ "revision": 5 }`. `bob.json` `connections` gains the
mirrored pair — `<b-doc-C>` posward `<a-doc-A>`, and `<a-doc-A>` negward
`<b-doc-C>` — **both records stored in `bob.json` only**, keyed on Bob's own
dimension. `alice.json` remains completely unchanged: Alice's cell now has a
neighbor from Bob's point of view, and no neighbor at all from her own.

### 9.21 TC-19 — Bob renders his view including Alice's cell

**Request**: `GET /structures/BOB/view?accursed=<b-doc-C>&view=h-view&x=<b-dim-related>&y=D.VIEWS`, bearer `BOB`.
**Expected**: `200`, `placedCells` includes `{ "cellId": "<a-doc-A>", "x": 1, "y": 0, "z": 0, "isVirtualCopy": false }`, and `cells["<a-doc-A>"]` in the response carries `"ownerId": "ALICE"` so a client can render it as foreign.

### 9.22 TC-20 — Alice's own view is unaffected

**Request**: `GET /structures/ALICE/view?accursed=<a-doc-A>&view=h-view&x=<a-dim-journal>&y=D.VIEWS`, bearer `ALICE`.
**Expected**: `200`, `placedCells` shows only `<a-doc-A>`/`<a-doc-B>` along `user.journal` — no trace of Bob's link, confirming isolation.

### 9.23 TC-21 — Bob unlinks the cross-user edge

**Request**: `DELETE /structures/BOB/links`, bearer `BOB`,
body `{ "a": "<b-doc-C>", "b": "<a-doc-A>", "dimension": "<b-dim-related>" }`.
**Expected**: `{ "revision": 6 }`. `bob.json` connection pair cleared.
`alice.json` unaffected (it never had a record of this edge to begin with).

### 9.24 TC-22 — Unlinking a non-existent edge

**Request**: repeat TC-21's request.
**Expected**: `404 { "error": "no_such_connection" }`.

### 9.25 TC-23 — Alice clones a cell

**Request**: `POST /structures/ALICE/clones`, bearer `ALICE`,
body `{ "of": "<a-doc-A>" }`.
**Expected**: `{ "cloneCellId": "<a-clone-1>", "revision": 6 }`. `alice.json`
`cells` gains `{ "id": "<a-clone-1>", "kind": "clone", "of": "<a-doc-A>", "ownerId": "ALICE" }`; `connections` gains a `D.CLONES`-colored pair linking `<a-doc-A>` posward to `<a-clone-1>`.

### 9.26 TC-24 — Export matches the file exactly

**Request**: `GET /structures/ALICE/export`, bearer `BOB` (export is a read, open cross-user).
**Expected**: `200`, response body deep-equal to the current contents of `data/alice.json`.

### 9.27 TC-25 — Optimistic concurrency conflict

**Request**: `POST /structures/ALICE/links`, bearer `ALICE`,
body `{ "a": "<a-doc-B>", "b": "<a-clone-1>", "dimension": "<a-dim-journal>", "expectedRevision": 1 }`
(stale — Alice's structure is actually at revision 6 by this point).
**Expected**: `409 { "error": "revision_conflict" }`. No mutation applied.

### 9.28 TC-26 — Importing a cell that doesn't exist

**Request**: `POST /structures/BOB/foreign-cells`, bearer `BOB`,
body `{ "foreignCellId": "00000000-0000-7000-8000-999999999999", "ownerId": "ALICE" }`.
**Expected**: `404 { "error": "foreign_cell_not_found" }`.

### 9.29 TC-27 — Unknown structure id

**Request**: `GET /structures/33333333-3333-7333-8333-333333333333/dimensions`, bearer `ALICE`.
**Expected**: `404 { "error": "unknown_structure" }` — checked before any read/write authorization logic runs.

## 10. Out of scope / future work

- Replacing the file-based persistence adapter with a database or
  object-store adapter behind the same `load`/`save` contract, without
  touching `engine.js`.
- A visibility policy for cross-user reads (currently unconditional between
  the two seeded users).
- A backlink index so Alice can discover that Bob has linked to one of her
  cells (nothing in this POC notifies her).
- Extending `authorization.json` and the persistence adapter's `userId ->
  file` map to support more than two users without code changes.
