# hypercore-cljs-poc

Two related terminal proof-of-concepts:

1. **`src/poc/core.cljs`** — a minimal demo that talks directly to the
   [Hypercore](https://www.npmjs.com/package/hypercore) npm package,
   the append-only-log primitive underneath the Pears/Holepunch
   decentralized stack (Pear, Bare, Hyperbee, Hyperdrive, Hyperswarm,
   Corestore, etc).
2. **`src/poc/pluggable.cljs`** — the same demo rewritten against a
   protocol-based abstraction layer (`src/app/`), so the *application*
   code no longer knows or cares whether it's talking to Hypercore or
   to a pure-Clojure mock. This is the one to read first if you want
   the abstraction, not just the Hypercore call-through.

## The abstraction layer (`src/app/`)

```
src/app/
  protocols.cljs           -- PAppendLog, PBackend (the whole abstraction)
  factory.cljs              -- picks an adapter by keyword
  adapters/
    hypercore.cljs           -- real Hypercore, via the npm package
    mock.cljs                -- pure Clojure, atoms only, no I/O at all
```

**`app.protocols/PAppendLog`** is the lowest common denominator every
decentralized-log-like backend can support: append, get, length,
byte-length, watch-for-new-blocks, and an opaque address. It's
deliberately shaped like Hypercore's own core API, because Hyperbee
(ordered KV) and Hyperdrive (filesystem) are themselves layered on top
of exactly this primitive — so anything that can satisfy `PAppendLog`
is a candidate backend, and higher-level abstractions (a `PKeyValueStore`,
a `PFileTree`) could be added the same way without touching this one.

**`app.protocols/PBackend`** bundles the two things that genuinely differ
per technology: how you create a pair of linked writer/reader logs, and
how you wire up replication between them. Everything else is identical
regardless of backend.

**Adapters** (`app.adapters.hypercore`, `app.adapters.mock`) are the
only namespaces allowed to know a specific technology exists. Each one
is `extend-protocol`'d onto its own record type and lives entirely
behind `PAppendLog`/`PBackend`. Adding IPFS, Hyperdrive, a Solid pod, or
anything else means adding one more file here — nothing in
`poc/pluggable.cljs` changes.

**`app.factory/create-backend`** is a plain keyword-dispatched switch
(`:hypercore` → real Hypercore, `:mock` → in-memory). Swapping the
underlying decentralized technology is a config/CLI-arg change, not a
code change:

```bash
npx nbb src/poc/pluggable.cljs mock       # pure Clojure, no network, no npm P2P deps
npx nbb src/poc/pluggable.cljs hypercore  # the real thing
```

Both commands run the exact same `poc/pluggable.cljs` — verified by
actually running both during development of this POC, not just by
reading the code.

### Why a mock backend, specifically

`app.adapters.mock` implements `PAppendLog`/`PBackend` with nothing but
Clojure atoms — no npm package, no native module, no network socket.
It exists so the application (and any tests you write against it) can
run in places real decentralized infrastructure can't reach: sandboxes,
CI, offline development, or anywhere you'd rather not stand up a P2P
stack just to test application logic. It's also the sharpest test of
whether the abstraction actually abstracts anything: if application
code needs to change to run against the mock, the abstraction has a
leak.

One deliberate detail: the mock replicates on a `setTimeout`, not
synchronously inside `log-append!`. Real replication is
latency-bound and out-of-band; if the mock delivered instantly and
synchronously, application code could accidentally depend on that and
then break the moment you pointed it at a real backend across a real
network. The 50ms shutdown grace period in `poc/pluggable.cljs`'s
`close` handler exists for the same reason — draining in-flight
replication before exit is a real concern with any backend, not a mock
artifact.

## Running it

Built and tested with **nbb** (ClojureScript on Node via SCI — no JVM
required):

```bash
npm install
npx nbb src/poc/pluggable.cljs mock        # or: hypercore, or: core.cljs directly
```

Type some lines, watch peer B receive them, `Ctrl+D` to quit.

`nbb.edn` sets `:paths ["src"]` so the multi-namespace `app.*` structure
resolves correctly; without it nbb only sees the single file you invoke.

### Alternative: shadow-cljs

`src/poc/core.cljs` (the original single-file demo) also compiles under
[shadow-cljs](https://shadow-cljs.github.io/docs/UsersGuide.html) if you
have a JVM and normal (non-restricted) internet access, since shadow-cljs
downloads Clojure/ClojureScript jars from Maven Central on first run:

```bash
npm install
npx shadow-cljs compile app
node out/main.js
```

The multi-namespace `app.*`/`poc.pluggable` structure will also compile
under shadow-cljs with the same `:paths`/source-root convention — this
wasn't verified in this sandbox (shadow-cljs itself couldn't run here;
see below), so treat that path as "should work, not yet confirmed."

nbb is a SCI-based interpreter, not the full self-hosted CLJS compiler —
notably it doesn't support custom macros — but everything used here
(namespaces, protocols, records, npm interop, promises) runs identically
under both.

## What was and wasn't actually verified

Everything under **"Running it"** above was executed in this sandbox
and its output inspected — not just written and assumed to work. The
one exception is the shadow-cljs path, which needs Maven Central access
this sandbox's network policy blocks.

## Where to go from here

- Add a `PKeyValueStore` protocol (mirroring Hyperbee) or `PFileTree`
  (mirroring Hyperdrive) alongside `PAppendLog`, with a generic
  KV-over-log implementation for any backend that only offers the log
  primitive natively.
- Add an `app.adapters.ipfs` (HTTP-API based) or `app.adapters.hyperdrive`
  adapter — same shape as the two here, nothing else changes.
- For real cross-machine replication instead of one process talking to
  itself, replace `backend-link!`'s direct `.pipe` wiring with an actual
  transport: a TCP socket, or Hyperswarm
  (`swarm.join(topic)` / `swarm.on('connection', stream => core.replicate(stream))`)
  for NAT-punching peer discovery over the DHT.
- Swap `random-access-memory` for a directory path so real-backend data
  persists across runs.
- Write actual tests against `app.adapters.mock` and reuse them
  unmodified (same assertions, same test bodies) against
  `app.adapters.hypercore` — the strongest evidence the abstraction is
  sound is application/test code that never needs to know which one it's
  talking to.

## Files

- `src/poc/core.cljs` — original single-backend Hypercore demo.
- `src/poc/pluggable.cljs` — same demo, backend-agnostic via `src/app/`.
- `src/app/protocols.cljs` — `PAppendLog`, `PBackend`.
- `src/app/factory.cljs` — keyword → adapter dispatch.
- `src/app/adapters/hypercore.cljs` — real Hypercore adapter.
- `src/app/adapters/mock.cljs` — dependency-free mock adapter.
- `nbb.edn` — classpath config (`:paths ["src"]`).
- `shadow-cljs.edn` — shadow-cljs build config (optional path).
- `package.json` — npm dependencies (`hypercore`, `random-access-memory`,
  `nbb` as a dev dependency).

