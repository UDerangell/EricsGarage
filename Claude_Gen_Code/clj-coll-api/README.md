# Collection Inventory API (Proof of Concept)

A small Ring/Compojure REST API on top of an in-memory Datomic database,
implementing the object model from our design discussion: items (including
containers), locations, photo linkage, checkout-style movements, and typed
connections between informational entities.

**This was written but not executed in the sandbox it was generated in** —
that environment's network allowlist covers npm/pip/crates but not
Clojars/Maven Central, so `com.datomic/datomic-free` and `midje` couldn't be
downloaded to run it. The code is complete and internally consistent; run it
locally with the steps below.

## Running it

Requires the Clojure CLI (`clj`) and internet access to Maven Central /
Clojars.

```bash
# start the server on :3000
clj -M:run

# run the Midje test suite
clj -M:test
```

## Design choices carried over from the discussion

- **Containers are items, not a separate type.** `:item/current-location` is
  an untyped ref — it can point at a `Location` (a shelf, a room) or at
  another `Item` acting as a container (a box). Moving a box implicitly moves
  everything inside it; `GET /items/:id/contents` walks that recursively via
  a Datalog rule.
- **Movements are the checkout ledger.** Every location change writes a
  `:movement` fact (item, from, to, reason, optional due-date/notes) *and*
  advances the fast `:item/current-location` pointer, in one transaction.
  `POST .../checkout` and `POST .../checkin` are just `move-item!` with a
  fixed `:reason`; `PUT .../location` is the general-purpose relocate.
  `GET .../history` replays `d/history` rather than maintaining its own log.
- **Photos are many-to-many.** `:photo/items` is `cardinality/many`, so one
  photo (a shelf shot) can tag several items, and one item can have several
  photos.
- **Connections are reified.** A plain ref can't carry "why are these two
  things related," so `:connection/*` is its own entity with `:from`, `:to`,
  `:type`, `:note`, `:confidence`. `GET /items/:id/connections` checks both
  directions via a rule, so a connection is discoverable from either side.
- **Simplification vs. the full design:** `:connection/type` is stored as a
  plain keyword here rather than a ref to a `:relation-type` entity. The
  fuller version (letting new relationship kinds be added as data, with a
  human label and a `symmetric?` flag) is a straightforward extension —
  add the `:relation-type` schema from the earlier design and swap the
  keyword for a lookup ref.

## Endpoints

| Method | Path                        | Purpose                                      |
|--------|-----------------------------|-----------------------------------------------|
| POST   | `/items`                    | create an item (optionally placed at a location or inside a container item) |
| GET    | `/items/:id`                | fetch an item, with current location resolved |
| PUT    | `/items/:id/location`       | relocate an item (`to-location-id`, `reason`) |
| POST   | `/items/:id/checkout`       | move item to a person/external location, with optional `due-date` |
| POST   | `/items/:id/checkin`        | move item back, recorded with reason `returned` |
| GET    | `/items/:id/history`        | full movement history, derived from `d/history` |
| GET    | `/items/:id/contents`       | recursive contents, if this item is a container |
| POST   | `/locations`                | create a location (room/shelf/person/etc.) |
| POST   | `/photos`                   | create a photo and link it to one or more items |
| GET    | `/items/:id/photos`         | photos linked to an item |
| POST   | `/connections`              | create a typed connection between two items |
| GET    | `/items/:id/connections`    | connections involving an item, from either side |

All bodies/responses are JSON; ids are UUID strings.

### Example: checking out a camera

```bash
curl -s -X POST localhost:3000/items \
  -H 'Content-Type: application/json' \
  -d '{"name":"Vintage Camera","category":"camera"}'
# => {"item/id":"...", "item/name":"Vintage Camera", ...}

curl -s -X POST localhost:3000/locations \
  -H 'Content-Type: application/json' \
  -d '{"name":"Alex'"'"'s House","type":"person"}'
# => {"location/id":"...", ...}

curl -s -X POST localhost:3000/items/<item-id>/checkout \
  -H 'Content-Type: application/json' \
  -d '{"to-location-id":"<location-id>","due-date":"2026-10-15T00:00:00Z"}'
```

## Files

```
deps.edn
src/collection/schema.clj   ; Datomic attribute definitions
src/collection/db.clj       ; connection lifecycle (init!, transact!, db)
src/collection/api.clj      ; handlers, Datalog rules, routes, middleware
src/collection/core.clj     ; -main, boots Jetty on :3000
test/collection/api_test.clj ; Midje tests, driven through the HTTP layer via ring-mock
```
