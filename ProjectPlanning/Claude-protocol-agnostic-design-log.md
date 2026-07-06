# Design Log: Clojure(Script) Access to Decentralized Data (Pears/Hypercore Stack)

**Status:** Best-effort reconstruction, not a raw export.

This document was written by Claude *after the fact*, from what was still in its
own context window, at the user's request. It is **not**:
- a verbatim dump of the underlying conversation transcript, or
- a verbatim dump of Claude's internal extended-thinking tokens.

Claude does not have a tool that exports either of those directly (no transcript
file was available on disk in this environment). What follows is a faithful,
human-written reconstruction of the actual reasoning trail — including dead
ends, bugs hit, and why specific design choices were made — assembled from the
visible turns, tool calls, and test output that occurred during the session.
Where a claim below was *actually verified by running code* rather than
asserted from memory, it's marked ✅ **verified**. Where something was written
but not run, it's marked ⚠️ **unverified**.

---

## 1. Scoping the problem: what is "the Pears.com stack"?

**Question asked:** how can a Clojure app access decentralized data using the
stack at Pears.com?

**Key research finding:** Pears.com refers to Holepunch's P2P stack — the
`Pear` runtime/CLI, the `Bare` JS runtime underneath it, and the data
primitives built on `libudx`/`libuv`: **Hypercore** (append-only log),
**Hyperbee** (ordered KV on top of Hypercore), **Hyperdrive** (filesystem on
top of Hyperbee), **Corestore** (multi-core storage manager), and
**Hyperswarm** (DHT-based peer discovery / NAT traversal).

**Design decision:** this is fundamentally a **JavaScript-native** stack —
Bare is a JS runtime, and Hypercore/Hyperswarm are npm packages backed by
native addons. That constrains how Clojure can reach it:

| Clojure flavor | Path in |
|---|---|
| ClojureScript | Compiles to JS; can run *inside* Bare/Pear (same CommonJS/ESM module resolution) or on plain Node, and can directly `require` the hyper* npm packages via interop. |
| Clojure (JVM) | No native binding exists — Hypercore's wire protocol isn't implemented on the JVM. Only indirect paths: shell out to a JS/Bare subprocess, run a sidecar process exposing RPC/HTTP, or use `nbb` (SCI-based ClojureScript on Node) as a middle ground. |

This scoping decision — **ClojureScript for anything touching the stack
directly, JVM Clojure only via a subprocess/RPC boundary** — shaped everything
that followed, since all later work targeted ClojureScript rather than trying
to force a JVM binding into existence.

---

## 2. First POC: a terminal ClojureScript app speaking real Hypercore

**Goal:** prove — not just claim — that ClojureScript can drive the actual
Hypercore replication protocol.

### 2.1 Initial plan vs. actual environment constraint

The original plan was **shadow-cljs** (the standard ClojureScript build tool)
targeting `:node-script`. This failed in the sandbox:

```
DependencyResolutionException ... repo1.maven.org/maven2/ ... Forbidden
```

**Root cause:** shadow-cljs needs a JVM and downloads its Clojure/CLJS jars
from Maven Central on first run. This sandbox's network allowlist includes
npm/PyPI/crates/GitHub but not Maven Central, so shadow-cljs could never
complete its first build here — a genuine environment constraint, not a code
bug.

**Design pivot:** switched to **nbb** — ClojureScript-flavored code
interpreted via SCI directly on Node, distributed as a plain npm package. This
unblocked local execution entirely (no JVM, no Maven) while keeping the same
language and the same npm interop story. The tradeoff, documented explicitly
for the user: nbb doesn't support the full self-hosted CLJS compiler (notably,
no custom macros), but everything this project actually uses — namespaces,
protocols, records, promises, npm interop — runs identically under both. The
shadow-cljs config was *kept in the project* (for use on a machine with normal
internet access) rather than deleted, but is explicitly labeled unverified
here.

### 2.2 A real interop quirk: CJS default-export wrapping differs by runtime

✅ **Verified via a small isolated test before writing the real app.**

Plain `node -e "require('hypercore')"` returns the constructor function
directly. Under nbb's ESM-based module loader, the same `require` returns a
Module-namespace object where the constructor is at `.default`:

```
Error: [object Module] is not a constructor
```

**Design decision:** rather than special-case this per-runtime, use a
one-line defensive unwrap that's a no-op under plain CJS and correct under
nbb's ESM interop:

```clojure
(def Hypercore (or (.-default HypercoreMod) HypercoreMod))
```

This pattern is used everywhere an npm default export is consumed, precisely
*so* the same source file behaves correctly whether run by nbb or (later,
theoretically) shadow-cljs.

### 2.3 Demo architecture: real protocol, deliberately short wire

**Design decision:** rather than trying to stand up Hyperswarm/DHT peer
discovery (which needs real network access and is nondeterministic — bad for
a demo meant to run in a sandbox), the POC creates two Hypercore instances in
one process (Peer A = writer, Peer B = reader opened against Peer A's public
key) and pipes their `.replicate()` streams directly into each other:

```
Peer A ⇄ replicate(true) ──pipe── replicate(false) ⇄ Peer B
```

This is explicitly *not* a simulation — `.replicate()` returns a real
Hypercore-protocol duplex stream; piping two of them together locally is
functionally identical to what a TCP socket or Hyperswarm connection would do,
just with the transport layer swapped for the shortest possible wire. This
distinction (real protocol, fake transport) was called out to the user
directly, since it's the difference between "a good demo" and "a lie about
what was actually tested."

### 2.4 Verification, not assertion

✅ **Verified**: `.ready()`, `.append()`, `.replicate()` + pipe, `"append"`
event, `.get()` — the full write→replicate→read cycle — were run with piped
stdin (`printf 'hello over hypercore\n' | npx nbb src/poc/core.cljs`) and the
output was inspected line-by-line before the file was considered done,
including catching that `.append()` resolves to `{length, byteLength}`, not a
bare integer, in this hypercore version.

---

## 3. Design discussion: a protocol-agnostic abstraction layer

**Question asked:** how would Clojure design an abstraction so *any*
decentralized-data technology (not just Hypercore) can be plugged in?

This turn was discussion/design only — no code was run — but the decisions
made here directly shaped the second POC (§4), so they're recorded as design
rationale:

1. **Layer by capability, not by backend.** Hypercore/Hyperbee/Hyperdrive
   aren't three unrelated APIs — Hyperbee is a B-tree on Hypercore, Hyperdrive
   is a filesystem on Hyperbee. So the abstraction should mirror that: one
   protocol for the lowest-common-denominator append-log primitive, with
   higher-level protocols (KV, filesystem) layered on top — rather than one
   flat interface trying to cover everything any backend might offer.

2. **Use `defprotocol`/`extend-protocol`, not a single fat interface.**
   Idiomatic Clojure open dispatch: each backend gets its own record type,
   `extend-protocol`'d onto the shared protocols. No backend's namespace is
   known to any other backend's namespace or to application code.

3. **Capability should be discoverable (`satisfies?`), not assumed.** Not
   every backend offers every protocol; backends that only offer the log
   primitive can still be used behind higher-level protocols via a generic
   wrapper built purely on the log protocol (mirroring how real Hyperbee is
   "just" a generic B-tree over a generic log).

4. **Standardize the async boundary.** Every backend has a different native
   async style (JS promises, JVM futures, callbacks). Rather than let each
   adapter leak its own async type into application code, pick one lingua
   franca all protocol methods return. (`core.async` channels were proposed
   in discussion; in the actual implementation in §4, this became **plain JS
   Promises** instead — `cljs.core.async` turned out not to be available
   under nbb, verified directly rather than assumed — see §4.1.)

5. **A config/keyword-driven factory** (multimethod or simple `case`) selects
   the concrete backend, so swapping technology is a config change.

6. **A pure in-memory adapter is the real test of the abstraction.** If
   application code needs to change to run against a dependency-free mock,
   the abstraction has a leak. This principle directly motivated building the
   mock adapter in §4, not just describing it.

---

## 4. Second POC: extending the demo with a pluggable abstraction + mock backend

**Goal:** make §2's demo backend-agnostic per §3's principles, and add a
mock backend that needs no real decentralized tech at all, specifically so
the whole thing can run in this sandbox.

### 4.1 Async lingua franca: plan vs. reality

**Planned:** `cljs.core.async` channels, per the design discussion in §3.

✅ **Verified this wasn't available before committing to it:**
```
npx nbb: Could not find namespace: cljs.core.async
```

**Design decision (revised in response to the test result):** use plain JS
`Promise`s as the async boundary instead. Every `PAppendLog`/`PBackend`
method returns a Promise; the mock adapter wraps synchronous atom updates in
`js/Promise.` constructors and `js/Promise.resolve` so it satisfies the same
contract as the real, genuinely-async Hypercore adapter. This is a concrete
example of a design plan changing *because* it was tested rather than assumed.

### 4.2 The abstraction as built

```
src/app/
  protocols.cljs        -- PAppendLog, PBackend (the whole abstraction)
  factory.cljs           -- keyword -> adapter dispatch
  adapters/
    hypercore.cljs        -- real Hypercore, via npm
    mock.cljs              -- pure Clojure atoms, no I/O
```

`PAppendLog` — append/get/length/byte-length/on-append/address — deliberately
shaped like Hypercore's own core API, since it's meant to be the lowest common
denominator that Hyperbee- and Hyperdrive-like things are built on.

`PBackend` — create-writer/create-reader/link! — bundles exactly the two
things that differ per technology (how you create a linked pair, how you wire
replication) and nothing else.

`app.factory/create-backend` is a plain `case` on a keyword. The terminal app
(`poc/pluggable.cljs`) imports only `app.protocols` — it does not know
`hypercore` exists.

### 4.3 Bugs found by actually running it (not caught by inspection)

Three real bugs surfaced only because each version was executed and its
output inspected, not just read back:

1. **argv indexing.** `process.argv[2]` is the script path under `node
   script.js`, but under `npx nbb script.cljs arg`, argv looks like
   `[node, nbb-bin, script.cljs, arg]` — so `argv[2]` is *still* the script
   path, not the user's argument. First attempt read the wrong index and
   produced `Unknown backend: :src/poc/pluggable.cljs`. Fixed by locating
   the script-path element in argv (matching `\.(cljs|js)$`) and taking
   everything after it, so the same code works regardless of which runner
   put how many entries before the user's args.

2. **A real async race in the mock's replication.** The mock backend
   deliberately replicates via `setTimeout` rather than synchronously (see
   §4.4). First test run piped two lines into stdin and closed it
   immediately; the process exited via `process.exit(0)` in the readline
   `"close"` handler *before* the 15ms replication timers fired, so Peer B
   never printed anything — even though the data had been correctly queued.
   This is exactly the kind of bug the mock is supposed to catch (see §4.4)
   — fixed by giving the `close` handler a 50ms grace period before exiting.

3. **Double-invocation risk under shadow-cljs.** Both terminal apps call
   their own `main`/`-main` at the top level of the namespace (so they run
   immediately under nbb, which just executes a file top-to-bottom).
   shadow-cljs's `:node-script` target additionally requires an `:init-fn`
   to be specified and calls it after the namespace loads — which would
   invoke `main` a second time. Resolved with a `noop` stub function that
   `:init-fn` points to instead, documented inline as to why it exists.

### 4.4 Why the mock replicates asynchronously, on purpose

**Design decision, stated explicitly to the user:** the mock adapter could
have replicated synchronously inside `log-append!` — simpler code, and it
would have "worked" for a naive demo. It deliberately does not, because real
replication is latency-bound and out-of-band; if the mock delivered
instantly and synchronously, application code could silently come to depend
on that timing and then break the first time it was pointed at a real,
network-bound backend. Making the mock's timing *wrong in the same direction*
Hypercore's timing is wrong (i.e., "eventually, not instantly") is what makes
the mock a meaningful stand-in rather than a toy. The shutdown-race bug in
§4.3 point 2 is offered as direct evidence this design choice mattered in
practice, not just in theory.

### 4.5 What was verified for this POC

✅ **Verified**, each by piping input through the actual command and reading
output:
- `npx nbb src/poc/pluggable.cljs mock` — full write → (async, delayed)
  replicate → read cycle, mock backend, zero external dependencies.
- `npx nbb src/poc/pluggable.cljs hypercore` — identical application code,
  real Hypercore backend, same output shape.
- `npx nbb src/poc/pluggable.cljs` (no arg) — confirmed default-to-`:mock`
  fallback.
- `npx nbb src/poc/core.cljs` — confirmed the original single-backend demo
  from §2 still works unmodified after all of the above changes.

⚠️ **Not verified**: the `shadow-cljs.edn` build targets for the new
multi-namespace (`app.*`) layout. Written to the same conventions as the
working nbb path, but shadow-cljs itself could not run in this sandbox (see
§2.1), so this is "should work" rather than "confirmed to work." This caveat
is stated in the project's own README as well, not just here.

---

## 5. Summary of design principles that generalize beyond this project

1. **Scope by what's actually reachable.** Identify early which parts of a
   stack are JVM-reachable vs. which require crossing a language/runtime
   boundary, and design the boundary explicitly rather than pretending it
   isn't there.
2. **Abstract by capability tier, mirroring the real dependency structure**
   of the technologies being wrapped, rather than inventing a flat interface
   that doesn't reflect how the underlying stack is actually layered.
3. **Pick one async representation for the abstraction boundary**, and verify
   it's actually available in the target runtime before committing to it.
4. **A dependency-free mock implementation of the same abstraction is the
   real test of whether the abstraction leaks** — and it should intentionally
   reproduce the *timing characteristics* of the real thing (async, delayed),
   not just its data shape, or it will hide bugs instead of catching them.
5. **Run it.** Several of the decisions and fixes recorded above (the CJS
   `.default` interop quirk, the argv indexing bug, the shutdown race, the
   `.append()` return-shape surprise) were only discovered because code was
   actually executed and its output read, not because they were anticipated
   in advance.

---

## 6. Deliverables referenced in this log

- `hypercore-cljs-poc.zip` (delivered twice — once after §2, once after §4
  with the `app/` abstraction layer added), containing:
  - `src/poc/core.cljs` — §2's single-backend demo.
  - `src/poc/pluggable.cljs` — §4's backend-agnostic demo.
  - `src/app/protocols.cljs`, `src/app/factory.cljs`,
    `src/app/adapters/{hypercore,mock}.cljs` — the abstraction layer.
  - `nbb.edn`, `shadow-cljs.edn`, `package.json`, `README.md`.
