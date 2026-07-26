# zzStructure REST API — Proof of Concept Specification (v0.02)

## 0. Changelog from v0.01

- Added **Carol** as a third seeded user, playing the role of a licensed
  publisher/redistributor, alongside Alice and Bob.
- Renamed the `document` cell kind to **`documentHead`** (`DocumentCell` →
  `DocumentHeadCell`), and renamed its content field from `documentId` to
  **`VisualMetaDocumentID`** — an immutable cross-reference to the Visual
  Meta JSON that travels with the real document.
- Added a new cell kind, **`paragraph`** (`ParagraphCell`), carrying
  **`VisualMetaDocumentID`** and **`VisualMetaParagraphID`** — an immutable
  cross-reference to one paragraph inside that document's Visual Meta JSON.
- Renamed endpoint `POST /structures/{id}/documents` to
  `POST /structures/{id}/document-heads`; added a new endpoint
  `POST /structures/{id}/paragraphs`.
- **No changes to bootstrap, the seven system dimensions, or
  `schemaVersion`.** A document's paragraph ordering ("rank") is threaded
  using an ordinary user-owned dimension, created via the existing
  `addDimension` primitive and composed with the existing `link` primitive
  — exactly like any other chain in this system. This version required zero
  new engine primitives beyond the two new cell-creation endpoints.
- Content itself — the actual text of a document or paragraph — is still
  never stored in a zzStructure file, in this version or any other. A cell
  is a reference, not a payload. This was already true of `documentId` in
  v0.01 and remains true of `VisualMetaDocumentID`/`VisualMetaParagraphID`
  here.
- Added §10.2, a short list of caveats deferred to a future "transcopyright"
  extension (payment, entitlement, royalties, content custody). These are
  named, not designed, in this version.
- Extended the test plan (§9) with TC-28 through TC-38, covering Carol
  publishing a small catalog, Alice transcluding a whole document from it,
  Alice authoring a new document that cites one already-transcluded
  paragraph, and Bob authoring a document that transcludes both one of
  Alice's own paragraphs and the Carol-originated paragraph Alice cited —
  all using only primitives that already existed in v0.01.

## 1. Overview

This document specifies a proof-of-concept Node.js application that exposes
a REST API for three independent zzStructures — owned by Alice, Bob, and
Carol respectively — each persisted as a plain JSON file on the local
filesystem. The API lets each user manage their own structure (cells,
dimensions, connections) and read cell/connection data from any other
user's structure, so that all three can weave cells they discover in each
other's structures into their own, using dimensions they each control.

As of this version, a document may be represented either as a single opaque
cell (as in v0.01) or, when finer addressability is wanted, as a
**`DocumentHeadCell`** anchoring a **rank** of **`ParagraphCell`**s — the
paragraph-by-paragraph structure of the underlying Visual Meta-described
document, reproduced as a chain of cells. This lets a caller transclude an
entire document, or a single paragraph of one, using the same primitives
either way.

This is still a proof of concept: single Node process, localhost only, no
TLS, no real identity provider, three hardcoded users. The goal remains to
validate architecture and message shapes, not to ship a production
multi-tenant service — and, specifically for this version, not to implement
payment, entitlement, or royalty enforcement (§10.2).

## 2. Goals and non-goals

**In scope**

- A REST API, running on `http://localhost:PORT`, backed by three JSON
  files (`alice.json`, `bob.json`, `carol.json`) plus one authorization file
  (`authorization.json`).
- Bootstrapping each user's file with the standard zzStructure system
  scaffolding (the seven system dimensions, the `d.dimensions` ring, the `d`
  namespace, and the H-view/I-view registration) the first time that file
  is needed — unchanged from v0.01, and unaffected by anything in this
  version.
- UUID-based caller identification, validated against the authorization
  file, with single-writer enforcement (a caller may only mutate the
  structure whose id matches their own).
- Cross-user reads: any user may read any other's cells, dimensions, and
  rendered views.
- Cross-user linking: any user may copy a read-only reference to another
  user's cell into their own structure and link it along a dimension they
  own, without mutating the other user's file.
- **Paragraph-level addressability.** A document may be represented as a
  `DocumentHeadCell` anchoring a rank of `ParagraphCell`s, each an immutable
  cross-reference into that document's external Visual Meta JSON. Both the
  document-level and paragraph-level cross-reference ids are supplied once,
  at creation time, and never change thereafter.
- Cross-user transclusion chains at least two hops deep (Carol → Alice →
  Bob), built entirely from the existing single-hop `foreign-cells`/`links`
  primitives, with no new engine machinery — see §9's new test cases.

**Out of scope**

- Real authentication (OAuth, sessions, passwords). A bearer UUID is
  treated as sufficient proof of identity for this POC.
- Fine-grained read permissions (visibility settings, allow-lists, paid
  content gating). Every seeded user can read every other unconditionally,
  **including paragraph cells that a production system would gate behind
  payment.** This version establishes the *addressing* of paragraphs, not
  their protection — see §10.2.
- More than three users. The authorization file format supports more, but
  this spec's test plan only exercises Alice, Bob, and Carol.
- Networked/decentralized storage, or any of the wider docuverse extensions
  discussed separately, beyond the paragraph-addressing step taken here.
- Payment, entitlement checking, royalty tracking/accrual, license-authority
  validation, live (as opposed to one-time-copy) transclusion, and content
  custody/serving — collectively deferred to a future "transcopyright"
  extension. See §10.2 for the caveat list; none of these are designed in
  this version.
- A UI. This is API-only; a test script (or curl/Postman collection) is the
  intended client.

## 3. Architecture

```
/poc
  /data
    authorization.json      # who is allowed to call the API
    alice.json               # Alice's zzStructure snapshot
    bob.json                  # Bob's zzStructure snapshot
    carol.json                 # Carol's zzStructure snapshot
  /src
    server.js                 # HTTP entry point, route wiring
    auth.js                    # bearer-UUID lookup against authorization.json
    persistence.js             # load(userId) / save(userId, snapshot)
    engine.js                   # cells, dimensions, connections, link/unlink,
                                  #   rank, bootstrap, view layout (HView/IView)
    routes/
      structures.js
```

Unchanged from v0.01. The three-layer split (HTTP / domain engine /
persistence adapter) and the per-user in-memory `Map<userId, { snapshot,
mutex }>` process model are untouched by this version — `authorization.json`
simply lists a third user, and `persistence.js`'s static `userId -> file`
map grows a third entry. Nothing about paragraph cells or document heads
required new engine primitives; §9's new test cases are built entirely from
calls that already existed in v0.01 (`link`, `addDimension`, the
find-or-create pattern, and cross-structure cell import).

## 4. Data model

### 4.1 Cell

```json
{
  "id": "3ab21b4e-6f2a-7c31-9a10-0c1145ac0011",
  "kind": "documentHead",
  "VisualMetaDocumentID": "vm:doc:9781234567890",
  "ownerId": "11111111-1111-7111-8111-111111111111"
}
```

`kind` is a flat discriminator. The fields that accompany it depend on the
value:

| `kind` | additional fields |
|---|---|
| `documentHead` | `VisualMetaDocumentID: string` |
| `paragraph` | `VisualMetaDocumentID: string`, `VisualMetaParagraphID: string` |
| `dimension` | `dimensionId: uuid` |
| `view` | `viewId: string` |
| `namespaceHead` | `name: string` |
| `clone` | `of: uuid` (the cell it clones) |
| `plain` | — |

`ownerId` is always the UUID of the structure that minted this cell. A cell
present in a structure's file with an `ownerId` other than that structure's
own `ownerId` is a **foreign cell cache entry** — a read-only copy imported
via `POST /foreign-cells` (§7.10), unchanged in mechanism from v0.01.

**`documentHead` (renamed from `document` in v0.01).** `VisualMetaDocumentID`
is the cross-reference to the Visual Meta JSON that accompanies the actual
document — a PDF, a manuscript, a note file, whatever it is — wherever that
file actually lives. As in v0.01, zzStructure never stores the document's
content, only this reference to it. This id is supplied by the caller at
creation time and is treated as immutable for the lifetime of the cell.

**`paragraph` (new in this version).** `VisualMetaParagraphID` is the
cross-reference to one paragraph inside that same Visual Meta JSON, assigned
by Visual Meta at the time the document was published and never reassigned
thereafter. Because a `VisualMetaParagraphID` is only guaranteed unique
*within* its own document, a `paragraph` cell always carries its parent
document's `VisualMetaDocumentID` alongside it — the two together, not
either alone, are what let a future content-resolution step find the right
text. As with `documentHead`, no actual paragraph text is stored on this
cell; it is a reference, gated by nothing, in this version.

A document's **rank** — the paragraph-by-paragraph ordering of its content —
is represented the same way any other ordered sequence is represented in
this system: a chain of cells linked along a dimension, with the
`DocumentHeadCell` occupying position zero (the ring/chain has no separate
"root" concept; the head is simply the rank's first cell, with no negward
neighbor along that dimension). See §7.11 and §9's new test cases for a
worked example. No new dimension-management machinery was needed for this —
whichever user owns the document head creates one ordinary dimension (via
the existing `POST /dimensions`, §7.6) and reuses it across every rank they
build, exactly as `d.namespace-siblings` is one dimension reused across
every namespace's member chain in bootstrap (§5).

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

Unchanged from v0.01. Every dimension in a user's file is owned by that same
user — a dimension never appears in a structure it doesn't govern. This
version's document/paragraph ranks are ordinary dimensions under this same
rule: Carol's catalog rank dimension lives in `carol.json` and is Carol's to
govern; when Alice reconstructs part of that rank inside her own structure
(§9 TC-33), she necessarily does so along a dimension of her own, not
Carol's — dimension ownership doesn't travel with an imported cell.

### 4.3 Connection

Unchanged from v0.01. Stored twice per edge (once on each cell), mirrored by
`link`/`unlink`.

### 4.4 Snapshot (the on-disk file format)

Unchanged from v0.01, including `schemaVersion: 1` — this version adds new
`kind` values to the `cells` array but makes no structural change to the
snapshot envelope itself.

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
    },
    {
      "id": "44444444-4444-7444-8444-444444444444",
      "displayName": "Carol",
      "handle": "carol",
      "dataFile": "carol.json"
    }
  ]
}
```

Mechanism unchanged from v0.01 — this is simply a third entry in a list the
format already supported.

## 5. Bootstrap behavior

Unchanged from v0.01 in every respect, and now applied uniformly to a third
file. Bootstrap knows nothing about document heads or paragraphs — nothing
user-specific is seeded for any of the three users, Carol included. Her
catalog is built entirely through the ordinary API surface, starting from
the same bootstrapped scaffolding Alice and Bob start from (§9 TC-28
onward).

## 6. Authentication and authorization model

Unchanged from v0.01. The resolution order in §6 of v0.01 already
generalizes to any number of seeded users without modification; nothing
about paragraph or document-head cells introduces a new authorization
check in this version. (A payment/entitlement check on paragraph *content*
— as opposed to the existence and metadata handled here — is exactly the
kind of check deferred to §10.2.)

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
| 8 | POST | `/structures/{id}/document-heads` | caller === id | `cell(forDocumentHead:)` — **renamed from `/documents`** |
| 9 | POST | `/structures/{id}/paragraphs` | caller === id | `cell(forParagraph:)` — **new in this version** |
| 10 | POST | `/structures/{id}/foreign-cells` | caller === id | import a cached cell from another structure |
| 11 | GET | `/structures/{id}/export` | any known caller | full `Snapshot` |

Endpoints 1–7 and 10–11 are unchanged from v0.01 except for the
`documentHead`/`paragraph` vocabulary now possibly appearing in their
request/response bodies wherever a generic `cell` is returned (§7.1, §7.2).
Only #8 (renamed) and #9 (new) are described below; see v0.01 for the rest.

### 7.8 `POST /structures/{id}/document-heads` (renamed from `/documents`)

```json
// request
{ "VisualMetaDocumentID": "vm:doc:9781234567890" }
```

```json
// 200
{ "cellId": "<cellId>", "created": true, "revision": 1 }
```

`created: false` and the existing `cellId` if that `VisualMetaDocumentID`
already has a `documentHead` cell in this structure (find-or-create
semantics, unchanged in spirit from v0.01's `/documents`).

### 7.11 `POST /structures/{id}/paragraphs` (new)

```json
// request
{ "VisualMetaDocumentID": "vm:doc:9781234567890",
  "VisualMetaParagraphID": "vm:para:9781234567890:0002" }
```

```json
// 200
{ "cellId": "<cellId>", "created": true, "revision": 4 }
```

Find-or-create semantics keyed on the **compound** pair
`(VisualMetaDocumentID, VisualMetaParagraphID)` — either field alone is not
a unique key, since paragraph ids are only guaranteed unique within their
own document. `created: false` and the existing `cellId` if that exact pair
already has a cell in this structure.

This endpoint only mints the cell. Placing it into a document's rank — i.e.
linking it posward from the document head or from the previous paragraph —
is a separate `POST /links` call (§7.4 of v0.01), exactly like composing
any other chain in this system. There is no auto-linking; §9's new test
cases show the two calls used together.

`400 validation_error` if either field is missing or not a non-empty
string.

## 8. Error model

Unchanged from v0.01. No new error codes were needed: `/document-heads` and
`/paragraphs` both reuse the existing `400 validation_error` /
find-or-create pattern, and rank composition reuses the existing
`link`/`unlink` error paths (`self_link_forbidden`, `unknown_cell`,
`unknown_dimension`, `restriction_r_violation`, `revision_conflict`)
unchanged.

## 9. Test plan

### 9.1 Fixtures

All symbols from v0.01 (§9.1) still apply. This version adds:

| Symbol | Meaning |
|---|---|
| `CAROL` | `44444444-4444-7444-8444-444444444444` |
| `VMDOC1` | `"vm:doc:9781234567890"` — Carol's first catalog document |
| `VMPARA1-1`, `VMPARA1-2`, `VMPARA1-3` | Paragraph ids within `VMDOC1` |
| `VMDOC2` | `"vm:doc:9781234567891"` — Carol's second catalog document |
| `VMPARA2-1` | Paragraph id within `VMDOC2` |
| `<c-head-1>`, `<c-para-1-1/2/3>` | Carol's cells for `VMDOC1`, created TC-28/TC-30 |
| `<c-dim-catalog>` | Carol's `catalog.sequence` dimension, created TC-29, reused for both her documents |
| `<c-head-2>`, `<c-para-2-1>` | Carol's cells for `VMDOC2`, created TC-32 |
| `VMDOC-ALICE-1` | `"vm:doc:alice-commentary-001"` — Alice's own new document, TC-35 |
| `<a-head-c1>`, `<a-para-c1-before>`, `<a-para-c1-after>` | Alice's own cells for that document |
| `<a-dim-transclusion>` | Alice's dimension used to reconstruct Carol's whole rank, TC-33 |
| `<a-dim-c1>` | Alice's dimension for her own new document's rank, TC-35 |
| `VMDOC-BOB-1` | `"vm:doc:bob-review-001"` — Bob's own new document, TC-37 |
| `<b-head-r1>`, `<b-para-r1-intro>` | Bob's own cells for that document |
| `<b-dim-r1>` | Bob's dimension for his new document's rank, TC-37 |

Tests run in order, continuing directly on from v0.01's shared fixture
(TC-00 through TC-27 already applied). Carol's file is bootstrapped exactly
as Alice's and Bob's were in TC-00, and is otherwise untouched before TC-28.

### 9.28 TC-28 — Carol creates her first document head

**Request**: `POST /structures/CAROL/document-heads`, bearer `CAROL`,
body `{ "VisualMetaDocumentID": "vm:doc:9781234567890" }`.
**Expected**: `{ "cellId": "<c-head-1>", "created": true, "revision": 1 }`.
`carol.json` `cells` gains one `{ "id": "<c-head-1>", "kind": "documentHead", "VisualMetaDocumentID": "vm:doc:9781234567890", "ownerId": "CAROL" }`.

### 9.29 TC-29 — Carol creates a reusable rank dimension for her catalog

**Request**: `POST /structures/CAROL/dimensions`, bearer `CAROL`,
body `{ "name": "sequence", "namespace": "catalog" }`.
**Expected**: `{ "dimension": { "qualifiedName": "catalog.sequence", ... }, "revision": 2 }`.
This single dimension, `<c-dim-catalog>`, will be reused — as a set of
disjoint chains, never a single connected ring — for every document in
Carol's catalog, the same way `d.namespace-siblings` is reused across every
namespace's member chain (§4.1).

### 9.30 TC-30 — Carol creates three paragraph cells for her first document

**Requests**: three calls to `POST /structures/CAROL/paragraphs`, bearer
`CAROL`:
```json
{ "VisualMetaDocumentID": "vm:doc:9781234567890", "VisualMetaParagraphID": "vm:para:9781234567890:0001" }
{ "VisualMetaDocumentID": "vm:doc:9781234567890", "VisualMetaParagraphID": "vm:para:9781234567890:0002" }
{ "VisualMetaDocumentID": "vm:doc:9781234567890", "VisualMetaParagraphID": "vm:para:9781234567890:0003" }
```
**Expected**: three `{ "cellId": "<c-para-1-1|2|3>", "created": true, "revision": 3|4|5 }` responses, in order. `carol.json` `cells` gains three `paragraph` cells, each carrying both `VisualMetaDocumentID` and its own `VisualMetaParagraphID`.

### 9.31 TC-31 — Carol links her document head and paragraphs into a rank

**Requests**: three calls to `POST /structures/CAROL/links`, bearer `CAROL`,
along `<c-dim-catalog>`:
```json
{ "a": "<c-head-1>", "b": "<c-para-1-1>", "dimension": "<c-dim-catalog>" }
{ "a": "<c-para-1-1>", "b": "<c-para-1-2>", "dimension": "<c-dim-catalog>" }
{ "a": "<c-para-1-2>", "b": "<c-para-1-3>", "dimension": "<c-dim-catalog>" }
```
**Expected**: three `{ "revision": 6|7|8 }` responses. `carol.json`
`connections` now describes the chain `<c-head-1> → <c-para-1-1> →
<c-para-1-2> → <c-para-1-3>` along `<c-dim-catalog>` — Carol's first
catalog document, fully ranked.

### 9.32 TC-32 — Carol adds a second document to her catalog

**Requests**: `POST /document-heads` for `VMDOC2` → `<c-head-2>`; one
`POST /paragraphs` for `VMPARA2-1` → `<c-para-2-1>`; one `POST /links`
`{ "a": "<c-head-2>", "b": "<c-para-2-1>", "dimension": "<c-dim-catalog>" }`.
**Expected**: all succeed; `revision` continues climbing. This chain is
disjoint from `VMDOC1`'s — both thread through `<c-dim-catalog>`, but
`<c-head-1>` and `<c-head-2>` never connect to each other. Carol's catalog
now contains two documents, confirming the shared-dimension pattern from
§4.1 scales to more than one work without new dimensions being minted per
document.

### 9.33 TC-33 — Alice transcludes Carol's whole first document

**Requests**:
1. Four calls to `POST /structures/ALICE/foreign-cells`, bearer `ALICE`,
   one per Carol cell (`ownerId: CAROL` in each body):
   `<c-head-1>`, `<c-para-1-1>`, `<c-para-1-2>`, `<c-para-1-3>`.
2. `POST /structures/ALICE/dimensions`, body
   `{ "name": "vmdoc-9781234567890", "namespace": "transclusion" }` →
   `<a-dim-transclusion>`.
3. Three `POST /structures/ALICE/links` calls reconstructing Carol's rank
   order inside `alice.json`, along `<a-dim-transclusion>`:
   `<a-head-1>→<a-para-1-1>→<a-para-1-2>→<a-para-1-3>` (these are the same
   cell ids as Carol's — `<c-head-1>` etc. — now cached in `alice.json`
   with `ownerId: CAROL`).

**Expected**: all eight calls succeed. `alice.json` gains four foreign
cache-entry cells (each `ownerId: CAROL`, unchanged from how they appear in
`carol.json`) and a new private dimension whose chain mirrors Carol's,
entirely inside Alice's own file. **`carol.json` is byte-for-byte
unchanged** throughout — the same key assertion as v0.01's TC-16/TC-18,
now demonstrated across four cells and three links instead of one.

Per §2 and §10.2, this transclusion is unconditional in this version — no
payment or entitlement check runs. "Alice purchases a complete document" is
represented here purely as "Alice imports and links every cell of it";
whatever a real purchase flow would gate is out of scope for this version.

### 9.34 TC-34 — Alice's view renders the transcluded document, correctly attributed

**Request**: `GET /structures/ALICE/view?accursed=<a-head-1>&view=h-view&x=<a-dim-transclusion>&y=D.VIEWS`, bearer `ALICE`.
**Expected**: `200`. `placedCells` includes all four cells in rank order;
`cells["<a-para-1-2>"].ownerId` (etc.) reads `"CAROL"` throughout, so a
client can render the whole document while correctly attributing it to its
original owner — the same mechanism v0.01's TC-19 used for a single cell,
unchanged here for a four-cell rank.

### 9.35 TC-35 — Alice writes a new document that cites an already-transcluded paragraph

**Requests**:
1. `POST /structures/ALICE/document-heads`, body
   `{ "VisualMetaDocumentID": "vm:doc:alice-commentary-001" }` →
   `<a-head-c1>`.
2. Two `POST /structures/ALICE/paragraphs` calls for her own new paragraphs
   (`vm:para:alice-commentary-001:0001` → `<a-para-c1-before>`;
   `vm:para:alice-commentary-001:0003` → `<a-para-c1-after>` — the gap at
   `:0002` is purely illustrative of where the citation sits; nothing in
   the system enforces or relies on paragraph-id numbering).
3. `POST /structures/ALICE/dimensions`, `{ "name": "commentary-001", "namespace": "user" }` → `<a-dim-c1>`.
4. Three `POST /structures/ALICE/links` calls along `<a-dim-c1>`:
   `<a-head-c1> → <a-para-c1-before> → <c-para-1-2> → <a-para-c1-after>`.

**Expected**: all calls succeed. Note step 4's middle link: `<c-para-1-2>`
is not re-imported — it is the exact cache entry TC-33 already created in
`alice.json`. Citing an already-transcluded paragraph costs Alice nothing
beyond a `link` call; no new `foreign-cells` call was needed, because the
cited cell was already present in her file. This is the mechanism behind
"that cited paragraph is a transclusion" from the use case: it is, quite
literally, the same foreign cache-entry cell participating in a second
rank.

### 9.36 TC-36 — Alice's new document renders with mixed ownership, correctly

**Request**: `GET /structures/ALICE/view?accursed=<a-head-c1>&view=h-view&x=<a-dim-c1>&y=D.VIEWS`, bearer `ALICE`.
**Expected**: `200`. `placedCells` shows all four cells of the new rank in
order; `cells["<a-head-c1>"].ownerId`, `cells["<a-para-c1-before>"].ownerId`,
and `cells["<a-para-c1-after>"].ownerId` all read `"ALICE"`, while
`cells["<c-para-1-2>"].ownerId` reads `"CAROL"` — one rank, two owners,
each correctly labeled.

### 9.37 TC-37 — Bob writes a document transcluding one of Alice's paragraphs and the Carol-originated citation

**Requests**:
1. `POST /structures/BOB/document-heads`, `{ "VisualMetaDocumentID": "vm:doc:bob-review-001" }` → `<b-head-r1>`.
2. `POST /structures/BOB/paragraphs`, `{ "VisualMetaDocumentID": "vm:doc:bob-review-001", "VisualMetaParagraphID": "vm:para:bob-review-001:0001" }` → `<b-para-r1-intro>`.
3. `POST /structures/BOB/foreign-cells`, body
   `{ "foreignCellId": "<a-para-c1-before>", "ownerId": "ALICE" }` — Bob
   imports one of Alice's own paragraphs directly.
4. `POST /structures/BOB/foreign-cells`, body
   `{ "foreignCellId": "<c-para-1-2>", "ownerId": "CAROL" }` — **note the
   `ownerId` here is `CAROL`, not `ALICE`**, even though Bob discovered this
   cell's id by reading Alice's document in TC-36. `GET`ting that cell (or
   Alice's rendered view) already showed `ownerId: "CAROL"` on it directly
   — Bob is importing from the cell's true, original owner, not through
   Alice as an intermediary. `foreign-cells` reads directly from whichever
   owner is named in the request; nothing about the chain Bob discovered it
   through is recorded or required.
5. `POST /structures/BOB/dimensions`, `{ "name": "review-001", "namespace": "user" }` → `<b-dim-r1>`.
6. Three `POST /structures/BOB/links` calls along `<b-dim-r1>`:
   `<b-head-r1> → <b-para-r1-intro> → <a-para-c1-before> → <c-para-1-2>`.

**Expected**: all calls succeed. `bob.json` ends up with cache entries for
one cell owned by `ALICE` and one owned by `CAROL`, both linked into a rank
alongside Bob's own two cells. **Both `alice.json` and `carol.json` remain
byte-for-byte unchanged** throughout — the same invariant TC-33 established
for a single hop now holds across a two-hop chain (Carol → Alice → Bob)
touching two different upstream owners in one rank.

### 9.38 TC-38 — Bob's rank renders with three-way attribution, and every upstream file is untouched

**Request**: `GET /structures/BOB/view?accursed=<b-head-r1>&view=h-view&x=<b-dim-r1>&y=D.VIEWS`, bearer `BOB`.
**Expected**: `200`. `placedCells` shows all four cells in rank order;
`ownerId` reads `"BOB"` for the head and intro paragraph, `"ALICE"` for the
imported paragraph, and `"CAROL"` for the citation — three owners in one
rank, each attributed correctly with no additional bookkeeping beyond what
`ownerId` already provides. A byte-for-byte diff of `alice.json` and
`carol.json` against their state at the end of TC-36/TC-32 respectively
shows no change: reading through a two-hop transclusion chain and building
on top of it never mutated anything upstream, at either hop.

## 10. Out of scope / future work

### 10.1 General POC limitations (unchanged from v0.01)

- Replacing the file-based persistence adapter with a database or
  object-store adapter behind the same `load`/`save` contract, without
  touching `engine.js`.
- A visibility policy for cross-user reads (currently unconditional among
  all seeded users).
- A backlink index so a user can discover that someone else has linked to
  one of their cells (nothing in this POC notifies them).
- Extending `authorization.json` and the persistence adapter's `userId ->
  file` map to support more than three users without code changes.
- The single-file-per-user, in-memory, one-mutex model this POC uses does
  not scale to a real catalog's size or read volume; a publisher-scale
  catalog is exactly the workload that would force the database-adapter
  question above sooner than anything else in this system.

### 10.2 Deferred: the transcopyright extension

The following are named here as known gaps, not designed. Building any of
them out is future work:

- **Payment and entitlement enforcement** — checking, for a specific
  requesting caller, whether they've paid for a specific paragraph before
  its content is returned (as opposed to this version's unconditional
  visibility of every cell's metadata to every seeded user).
- **Royalty tracking and accrual** — recording who is owed what, by whom,
  as paragraphs are purchased, and by which authority.
- **License-authority validation** — ensuring only Carol (or whoever
  actually holds redistribution rights for a given `VisualMetaDocumentID`)
  can mint canonical `documentHead`/`paragraph` cells referencing it, so
  that no other user can mint a competing, unlicensed claim to the same
  external identifier.
- **Live vs. one-time-copy transclusion, and content custody** — this
  version's `foreign-cells` import remains a static, one-time copy of a
  cell's identifying fields (unchanged from v0.01); it does not re-check
  anything on subsequent reads, and — because no cell in this system stores
  actual content — it says nothing about where the real text lives, who
  serves it, or how that service would honor whatever entitlement decision
  the zzStructure layer eventually computes.
- **Versioning of the underlying document** — `VisualMetaDocumentID` and
  `VisualMetaParagraphID` are immutable as *references*, but nothing here
  addresses what should happen if the content behind a reference is
  revised after the fact.
