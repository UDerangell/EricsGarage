Note to readers: Search for **Prompt:** to navigate to each prompt to find topics of interest.  There is an interesting story named "The Oaks Project" towards the end of the document that has ideas for AR collaborative workspaces.

Prompt: Please outline a project plan for building a server in Clojure that responds to a byte stream which contains keystrokes, mouse movements, and chord keyset chord values (5 bits: 0-31).  The server will respond to each command in the byte stream by serving a byte stream response to the caller based on the user account associated with the connection.  Design an extensible interface that will allow the user to select OPML documents from their directory on the server, navigate them in a manner similar to Douglas Engelbart's NLS system, and save their changes to newer versions of the OPML files, where older versions remain preserved in a Journal system.

# Project Plan: NLS-Inspired OPML Navigation Server in Clojure

## 1. System Overview

A stateful, connection-oriented server that accepts a binary input stream encoding three classes of user input (keystrokes, mouse movements, chord keyset values), interprets them as navigation/editing commands against a per-user OPML outline store, and emits a binary output stream representing screen/state deltas. Versioning is handled by an immutable Journal — every save creates a new version; nothing is overwritten.

This is architecturally similar to NLS: a chord-keyset + mouse + keyboard "tri-modal" input model, hierarchical outline documents, view-specific navigation commands (expand/collapse, jump to link, "viewspec" filtering), and a journal of permanent, addressable document versions.

---

## 2. Core Architectural Components

```
┌──────────────┐     ┌────────────────┐     ┌──────────────────┐
│  Transport    │────▶│ Protocol Codec │────▶│ Command Dispatch  │
│ (TCP/WebSocket)│     │ (byte stream)  │     │   (multimethod)   │
└──────────────┘     └────────────────┘     └──────────┬────────┘
                                                          │
                      ┌───────────────────────────────────┘
                      ▼
       ┌─────────────────────────────┐      ┌────────────────────┐
       │   Session / Account State    │◀────▶│  Outline Engine     │
       │ (per-connection atom/agent)  │      │ (OPML zipper model)  │
       └─────────────────────────────┘      └─────────┬──────────┘
                                                         │
                                              ┌──────────▼──────────┐
                                              │  Journal / Version   │
                                              │  Store (append-only) │
                                              └──────────┬──────────┘
                                                         │
                                              ┌──────────▼──────────┐
                                              │  Filesystem (per-   │
                                              │  user OPML dirs)     │
                                              └──────────────────────┘
```

Clojure favors this design naturally: immutable persistent data structures map directly onto "journal of versions," and `clojure.zip` gives a ready-made cursor abstraction for outline navigation.

---

## 3. Project Phases

### Phase 0 — Foundations & Project Scaffolding
- Set up `deps.edn` or Leiningen project, namespaces (`server.transport`, `server.protocol`, `server.session`, `server.outline`, `server.journal`, `server.commands`, `server.account`).
- Choose transport: raw TCP via `java.nio`/Netty wrapper (e.g. `aleph` or `manifold` + `netty`), or WebSocket if browser-based clients are anticipated. Aleph is a good Clojure-native fit for persistent byte-stream connections.
- Decide synchronous vs. async I/O model (recommend `manifold` streams: composable, backpressure-aware, good fit for continuous keystroke/mouse event flow).
- Set up test harness (`clojure.test` + a fake byte-stream generator for integration tests).

### Phase 1 — Wire Protocol Design
Define a compact binary framing format, since raw input events need low latency and the chord keyset is inherently bit-oriented.

- **Frame header**: 1 byte event-type tag + length-prefixed payload.
  - `0x01` Keystroke: payload = key code (2 bytes, supports modifiers via high bits) + event type (down/up).
  - `0x02` Mouse: payload = dx/dy (signed 16-bit each) + button state byte.
  - `0x03` Chord: payload = 1 byte, lower 5 bits = chord value (0–31), allowing extension bits in upper 3 bits (e.g. chord "shift" or repeat flag).
  - `0x04` Control/session frames (auth, connect-to-doc, heartbeat).
- **Response frame format**: similarly tagged — `0x80` outline-delta, `0x81` cursor-position, `0x82` error, `0x83` ack, `0x84` raw-render (e.g. serialized subtree for client redraw).
- Write encode/decode functions using `clojure.java.io` + `ByteBuffer`, or a `gloss`/`octet` library for declarative binary framing (recommended — reduces hand-rolled parsing bugs).
- Define this as a versioned protocol spec doc up front (`protocol.md`) since client and server must agree on it — write this as an artifact-style spec so it can evolve independently of code.

**Deliverable:** `server.protocol` namespace with pure `encode`/`decode` multimethods, plus round-trip tests.

### Phase 2 — Session & Account Model
- Each TCP/WebSocket connection maps to a `Session` record: `{:account-id, :conn-stream, :cursor-state, :current-doc, :mode}`.
- Account model: directory-per-user under e.g. `data/accounts/<user-id>/opml/`.
- Auth handshake: minimal — control frame with credentials/token at connection start; resolves to account dir and permission scope.
- Session state held in an `atom` per connection; consider `core.async` channels per session for command/response decoupling so input parsing and rendering can run concurrently.

**Deliverable:** `server.session` + `server.account`, with connection lifecycle (connect → authenticate → loop → disconnect) and tests using mock streams.

### Phase 3 — Outline Engine (the NLS core)
This is the heart of the system and deserves the most design care.

- **Document model**: parse OPML (XML) into a Clojure data structure — a tree of `{:text :attrs :children}` nodes, or directly into `clojure.zip` zippers for cursor-based traversal (this mirrors NLS's "current viewspec + location" model closely).
- **Cursor/viewspec state**: track current node, expand/collapse set, filter level (depth-limited views, similar to NLS's "level clipping"), and view mode (outline vs. flat).
- **Navigation commands** (mapped from chord values, in the spirit of NLS's single-handed chording for command selection):
  - move up/down sibling, in/out level, jump to link, expand/collapse subtree, search-by-text, "jump to first/last," bookmark/return.
  - Use a `defmulti dispatch-command` keyed on a normalized command keyword, decoupling chord-value-to-command mapping (configurable, remappable per account — extensibility point) from command semantics.
- **Editing commands**: insert node, delete node, promote/demote (outdent/indent), reorder siblings, edit text-in-place (driven by keystroke stream while in "edit mode").
- **Extensibility**: define a protocol `OutlineCommand` (or just multimethod dispatch with namespaced keywords) so new command types can be registered without modifying the dispatcher — e.g. `(defmethod dispatch-command :outline/expand-subtree [...])`. Keep a command-registry atom so plugins/extensions can `register-command!`.

**Deliverable:** `server.outline` namespace: zipper-based cursor ops, command multimethods, full unit test suite against sample OPML fixtures.

### Phase 4 — Journal / Versioning System
This is the "older versions remain preserved" requirement — treat it as an append-only, content-addressed store rather than in-place file mutation.

- **Storage layout** options (pick one, design for swappability):
  - Simple: `data/accounts/<user>/opml/<doc-id>/v{n}.opml` plus a `manifest.edn` listing version metadata (timestamp, author, diff summary, parent version).
  - Content-addressed: store each version blob keyed by SHA-256 hash, with a manifest mapping `doc-id -> [hash, hash, ...]` in order — enables dedup and integrity verification.
- **Write path**: edits accumulate in an in-memory "working" zipper; explicit save command snapshots the full tree, serializes to OPML, writes a new immutable version file, appends a manifest entry. Never mutates prior versions.
- **Journal API**: `(journal/save! account doc-id new-tree)`, `(journal/versions account doc-id)`, `(journal/load account doc-id version)`, `(journal/diff v1 v2)`.
- Consider modeling this like a mini Git: each version references its parent, enabling future branching/merging if needed — but keep v1 implementation linear/simple and only generalize if requirements demand it.
- Crash-safety: write-to-temp-then-rename for atomicity; consider an actual embedded transactional store (e.g. `datalevin` or even SQLite via `next.jdbc`) if file-based journaling proves fragile under concurrent access — flag this as a phase-4.5 evaluation point rather than committing upfront.

**Deliverable:** `server.journal`, with property-based tests (e.g. `test.check`) verifying that saving N versions never loses or corrupts prior ones, and that `load` always reconstructs an exact prior tree.

### Phase 5 — Command Dispatch & Server Loop Integration
- Wire protocol decode → session lookup → command translation (chord/key/mouse → outline command) → outline engine mutation → response encode → write to output stream.
- Build the chord-to-command mapping as **data**, not code (an EDN config per account or system-wide default), so the 32 chord values can be remapped — this is your main "extensibility" lever for the input side.
- Mouse movement handling: translate dx/dy + click state into outline operations (e.g. click selects node at rendered position — requires the server to track a "last rendered layout" per session so it can map screen coordinates back to outline nodes, much like NLS's mouse-to-text-position mapping).

**Deliverable:** `server.commands` orchestration layer; integration tests simulating full input-stream sessions against fixture OPML docs, asserting on output byte stream.

### Phase 6 — Extensibility Layer (formalize what's emerged organically above)
- Command registry protocol for third-party/future command types.
- Pluggable serialization: today OPML; design `server.format` as a protocol (`parse`, `render`) so future formats (Markdown outline, JSON) could be added without touching the outline engine.
- Pluggable storage backend protocol for the Journal (filesystem vs. DB vs. content-addressed blob store).
- Config-driven chord/key bindings per account.

### Phase 7 — Hardening, Concurrency, and Ops
- Concurrency model: one `core.async` go-loop or manifold stream per connection; shared mutable state (none, ideally — push everything through the session atom) avoided by design.
- Backpressure and malformed-frame handling (protocol errors should not crash the session).
- Logging/observability (`mulog` or simple structured logging) for command dispatch and journal writes.
- Load testing with synthetic byte streams (generate plausible keystroke/mouse/chord sequences).
- Security: path traversal protection on OPML directory access, account isolation, auth token expiry.

### Phase 8 — Documentation & Client Reference
- Protocol spec finalized as the canonical contract.
- A minimal reference client (even a CLI or small script) that can generate valid input frames and render the output stream, to validate the server independent of any real client implementation, and to give other developers a starting point.

---

## 4. Suggested Library Choices

| Concern | Library |
|---|---|
| Async networking | `aleph` / `manifold` |
| Binary framing | `gloss` or `octet`, or hand-rolled `ByteBuffer` |
| OPML/XML parsing | `clojure.data.xml` |
| Outline cursor | `clojure.zip` |
| Concurrency glue | `core.async` |
| Journal storage (if DB-backed) | `datalevin` or `next.jdbc` + SQLite |
| Testing | `clojure.test` + `test.check` for journal invariants |

---

## 5. Key Design Risks to Flag Early

A few things worth deciding deliberately before writing much code, since they shape everything downstream: whether mouse-to-node mapping requires the server to be layout-aware (stateful rendering model) or whether layout stays entirely client-side and the server only receives already-resolved node references; whether the Journal needs concurrent multi-writer support per document (locking strategy) or is single-session-per-document for v1; and how much of the chord/command mapping should be hot-reloadable versus requiring reconnect.

If it's useful, I can next draft the actual protocol byte-layout spec in detail, or scaffold the namespace structure with starter code for the outline zipper and journal save/load functions — let me know which you'd want to start with.

Prompt: The NLS system used several Domain-Specific languages that evolved over time to support NLS functionality.  How can Clojure macros be used to define DSLs ?

Clojure is unusually well-suited to building the kind of evolving, layered DSLs that NLS relied on (its command language, link/viewspec language, and L10 procedure language all grew incrementally over the system's life). Macros are the mechanism because they operate on *unevaluated code* at compile time, letting you introduce new syntax that compiles down to ordinary function calls — rather than being restricted to whatever functions and data literals the language already provides.

Here's how that maps onto your outline server, working from simple to more ambitious.

## Why macros rather than just functions

A function receives evaluated arguments — by the time it runs, `(+ 1 2)` has already become `3`. A macro receives the *unevaluated forms* — the literal `(+ 1 2)` — and returns new code, which is then evaluated. This is what lets you write things that look like new syntax: control structures, declarative bindings, little grammars — instead of always nesting normal function calls. For NLS-style systems, this matters because you want command definitions, viewspecs, and chord bindings to read like a domain notation, not like generic data-munging code.

## 1. A DSL for defining outline commands

Right now you might dispatch with a raw multimethod:

```clojure
(defmethod dispatch-command :outline/expand-subtree [session cmd]
  (swap! session update :cursor expand-subtree-at-cursor))
```

That's fine, but it's boilerplate-heavy once you have forty commands, each needing logging, permission checks, undo-journal hooks, etc. A macro lets you compress the *ceremony* while keeping the per-command logic explicit:

```clojure
(defmacro defcommand [name chord-binding [session-sym] & body]
  `(do
     (register-chord! ~chord-binding ~(keyword "outline" (str name)))
     (defmethod dispatch-command ~(keyword "outline" (str name))
       [~session-sym _cmd#]
       (log-command! ~session-sym ~(keyword "outline" (str name)))
       ~@body)))

(defcommand expand-subtree 5 [session]
  (swap! session update :cursor expand-subtree-at-cursor))

(defcommand outdent 12 [session]
  (swap! session update-in [:cursor :tree] outdent-node))
```

Each `defcommand` call expands into a chord registration *and* a multimethod implementation *and* logging, all from one declarative form. This is the same shape as NLS's evolving command-naming system: commands as first-class declared entities, not scattered case-statement branches. Critically, because it's a macro and not just a registration function, you get this wiring at *compile time* — typos in chord numbers or duplicate registrations can be caught with compile-time assertions inside the macro body.

## 2. A viewspec DSL

NLS viewspecs controlled which lines/levels were visible, in what order, with what numbering. A natural DSL:

```clojure
(defmacro defviewspec [name & {:keys [depth filter sort-by] :as opts}]
  `(def ~name (build-viewspec ~opts)))

(defviewspec compact-todo
  :depth 2
  :filter (fn [node] (contains? (:tags node) :todo))
  :sort-by :priority)
```

Here the macro is doing something subtly important: it lets `:filter` take a literal `fn` form that closes over nothing dangerous and gets embedded as code, while still letting the whole call look like a configuration record rather than a function invocation. You could go further and let `:filter` accept its *own* mini-language (e.g. `(filter (tag= :todo))`) that another macro expands into the predicate function — this is exactly how layered DSLs grow, each one compiling into the layer below it, mirroring how L10 sat on top of lower NLS layers.

## 3. Chord-binding DSL as data, but checked at compile time

You mentioned earlier wanting chord bindings to be data (EDN config) for runtime remapping — macros are a good complement here, not a replacement: use a macro at the "factory default" definition site to validate invariants statically (e.g. no chord value outside 0–31, no duplicate bindings) while still emitting plain data that a runtime EDN file can override:

```clojure
(defmacro chordmap [& pairs]
  (let [m (apply hash-map pairs)]
    (doseq [[chord cmd] m]
      (assert (<= 0 chord 31) (str "Invalid chord value: " chord)))
    m))

(def default-bindings
  (chordmap
    5  :outline/expand-subtree
    12 :outline/outdent
    19 :outline/jump-to-link))
```

The assertion runs once, at compile time, against the literal pairs you wrote — bad data gets caught when you build the project, not when a user happens to press that chord in production.

## 4. Where to draw the line

A few things worth keeping in mind so the macro layer doesn't become a maintenance trap:

**Prefer functions and data until a macro earns its place.** Most of what looks DSL-like (the chord bindings, the viewspec options) can just be plain maps and functions consumed by ordinary higher-order functions — `register-chord!`, `build-viewspec` — with the macro only adding compile-time validation or boilerplate elimination on top. If you can write it as data + a function, do that first; reach for `defmacro` only when you want new *syntax*, not just new *values*.

**Macros compose badly with dynamism.** Since macro expansion happens at compile time, a `defcommand`-defined chord binding can't be changed by an end user editing a config file at runtime — that has to be a separate, data-driven layer (which is exactly what you want for the account-level remapping you described earlier). Use macros for the *system's* extensibility (new command types, new viewspec grammar) and plain data for the *user's* extensibility (chord remapping, per-account preferences).

**Use `&env` and hygiene carefully if commands need to capture session context.** Clojure's syntax-quote (`` ` ``) auto-gensyms symbols to avoid variable capture, but if your macro needs to thread a session symbol through user-supplied body code (as `defcommand` does above with `session-sym`), make that contract explicit in the macro's argument list rather than relying on accidental capture — easier to debug and document.

**Consider `clojure.spec` alongside macros for DSL validation.** Once your command/viewspec DSLs get non-trivial, you'll want richer error messages than a bare `assert`. Specs can validate the shape of `defcommand`/`defviewspec` forms and give much better feedback when someone gets the grammar wrong — genuinely useful for a DSL that, like NLS's, will evolve and accumulate new option keywords over time.

If it'd help, I can sketch a fuller worked example — say, a small `defviewspec` macro that expands into actual `clojure.zip` predicate-building code, since that's the piece most directly tied to your outline engine from the earlier plan.

Prompt: In NLS the mouse had 3 buttons and 2 of them were used to change the "case" of the keyset chord, so the number 0-31 could represent lowercase, uppercase, symbols, or commands.  The remaining button can be used to register the mouse ("bug") location to be used for a command.  How would this requirement be implemented and tested with Clojure data structures?

This maps cleanly onto Clojure's strengths: a small enumerated state space (4 cases × 32 chords = 128 symbols), a separate "designation" mechanism (the third button capturing a screen/outline location), and pure functions that combine them — which makes the whole thing trivial to test with `clojure.test` and `test.check` since there's no hidden mutable state in the core logic.

## 1. Modeling the input state

Three physical things need representing: current chord value (0–31), mouse button state (which of the 3 buttons are down), and a "designated location" — the bug position latched by the third button.

```clojure
(ns nls.input)

;; Mouse button bitmask — button 0 and 1 are case modifiers, button 2 is "designate"
(def case-bit-left   0)  ;; bit 0
(def case-bit-right  1)  ;; bit 1
(def designate-bit   2)  ;; bit 2

(defn button-down? [button-state bit]
  (bit-test button-state bit))

;; The 2 case-modifier buttons give 4 combinations -> 4 cases.
;; This mirrors NLS's lowercase/uppercase/symbol/command shifting.
(def case-table
  {[false false] :lowercase
   [true  false] :uppercase
   [false true]  :symbol
   [true  true]  :command})

(defn current-case [button-state]
  (case-table [(button-down? button-state case-bit-left)
               (button-down? button-state case-bit-right)]))
```

`case-table` as plain data is the important move — it's not a `cond` chain, it's a lookup, so adding a fifth case later (say, if you ever wanted a chord+case combination beyond NLS's original four) is a one-line data change, not a logic change.

## 2. Combining chord + case into a resolved symbol

```clojure
(defn resolve-symbol
  "Given a chord value (0-31) and button-state, returns the keyword
   identifying which of the 128 possible symbols was entered."
  [chord button-state]
  {:pre [(<= 0 chord 31)]}
  (let [case-kw (current-case button-state)]
    [case-kw chord]))
```

Returning `[case-kw chord]` rather than eagerly mapping to a character keeps this layer pure and decoupled from the symbol-table lookup (which command/letter/digit each of the 128 combos means) — that's a separate concern, handled by a lookup table:

```clojure
(def symbol-table
  ;; Sparse example; full table would have 128 entries.
  {[:lowercase 1]  \a
   [:uppercase 1]  \A
   [:symbol    1]  \!
   [:command   1]  :cmd/expand-subtree})

(defn ->symbol [chord button-state]
  (get symbol-table (resolve-symbol chord button-state) :unknown))
```

## 3. The "bug" designation mechanism

The third button is structurally different — it's not a modifier composed with the chord, it's a *latch*: pressing it captures wherever the mouse currently is, and that captured location is then available to whatever command gets executed next (NLS's "designate, then act" pattern). Model that explicitly as session state, separate from the stateless chord/case logic above:

```clojure
(defrecord Designation [x y node-ref timestamp])

(defn designate!
  "Call when the designate button transitions down. Captures current
   mouse position (and, if resolvable, the outline node under it) into
   the session atom."
  [session-atom mouse-pos resolve-node-fn]
  (swap! session-atom assoc :designation
         (map->Designation
          (assoc mouse-pos
                 :node-ref (resolve-node-fn mouse-pos)
                 :timestamp (System/currentTimeMillis)))))

(defn current-designation [session-atom]
  (:designation @session-atom))
```

Commands that need a target location (e.g. "delete the designated node", "link here") just read `current-designation` rather than receiving a coordinate directly — this matches NLS's actual semantics, where designation persists across multiple subsequent commands until re-designated, rather than being consumed once like a function argument.

## 4. Wiring it into the byte-stream event loop

Given the protocol frames from the earlier plan, the event handler becomes a small dispatch:

```clojure
(defn handle-event [session-atom event]
  (case (:type event)
    :mouse-button
    (when (and (= (:button event) designate-bit) (:down? event))
      (designate! session-atom (:pos event) (partial node-at-screen-pos session-atom)))

    :mouse-button-case
    (swap! session-atom assoc-in [:input :button-state]
           (set-bit (get-in @session-atom [:input :button-state]) (:button event) (:down? event)))

    :chord
    (let [button-state (get-in @session-atom [:input :button-state])
          sym (->symbol (:value event) button-state)]
      (dispatch-symbol session-atom sym (current-designation session-atom)))))
```

The point of factoring it this way: `dispatch-symbol` always receives both the resolved symbol *and* whatever's currently designated, so e.g. a `:command` chord meaning "delete" can act on the designated node without needing the mouse-click and the chord-press to arrive in the same event or even be temporally close — which matches how NLS actually let you designate something, then think, then chord a command.

## 5. Testing strategy

The clean separation above is what makes testing easy — most of it is pure functions over plain data, so no mocking is needed for the core logic; only the designation/session layer needs a fixture atom.

**Pure logic — exhaustive/property-based:**

```clojure
(ns nls.input-test
  (:require [clojure.test :refer :all]
            [clojure.test.check :as tc]
            [clojure.test.check.generators :as gen]
            [clojure.test.check.properties :as prop]
            [nls.input :refer :all]))

(deftest case-table-covers-all-combinations
  (doseq [left [true false] right [true false]]
    (is (contains? case-table [left right])
        (str "missing case mapping for " left right))))

(deftest case-table-is-bijective
  ;; 4 distinct button combos must map to 4 distinct cases — guards
  ;; against an accidental duplicate value in the table.
  (is (= 4 (count (set (vals case-table))))))

(def chord-gen (gen/choose 0 31))

(deftest resolve-symbol-property
  (tc/quick-check 200
    (prop/for-all [chord chord-gen
                   left  gen/boolean
                   right gen/boolean]
      (let [bs (-> 0 (set-bit case-bit-left left) (set-bit case-bit-right right))
            [case-kw resolved-chord] (resolve-symbol chord bs)]
        (and (= resolved-chord chord)
             (contains? #{:lowercase :uppercase :symbol :command} case-kw))))))

(deftest chord-out-of-range-throws
  (is (thrown? AssertionError (resolve-symbol 32 0)))
  (is (thrown? AssertionError (resolve-symbol -1 0))))
```

The property test is the valuable one: rather than hand-writing 128 example cases, it asserts the *invariant* — every chord/button combination round-trips to a valid case and an unchanged chord value — across randomly generated inputs. This is exactly the kind of guarantee you want before wiring this into a live byte stream, where a malformed chord value should never silently produce garbage.

**Designation/session logic — state-based:**

```clojure
(deftest designate-captures-position-and-node
  (let [session (atom {})
        resolve-fn (constantly :node/42)]
    (designate! session {:x 100 :y 200} resolve-fn)
    (let [d (current-designation session)]
      (is (= 100 (:x d)))
      (is (= :node/42 (:node-ref d))))))

(deftest designation-persists-across-multiple-commands
  ;; Mirrors NLS semantics: designation is a latch, not consumed on first use.
  (let [session (atom {})]
    (designate! session {:x 1 :y 1} (constantly :node/a))
    (let [first-read (current-designation session)]
      (dispatch-symbol session [:command 5] first-read)  ;; some command runs
      (is (= first-read (current-designation session))   ;; still there afterward
          "designation should not be cleared by command dispatch"))))
```

**Integration test — full byte-stream simulation:** once the protocol codec from the earlier phases exists, build a fixture that feeds a literal sequence of frames (button-down on case bit, chord frame, button-down on designate bit at a position, another chord frame) through `handle-event` and asserts on the resulting session state and emitted response frames. This is the test that actually validates the NLS-like *interaction sequence* — designate-then-chord — rather than just the isolated pieces.

One design point worth flagging: because designation is a persistent latch rather than a one-shot argument, you'll want a test explicitly asserting it survives across an intervening unrelated chord (e.g. case-only chord changes shouldn't clear it) — that's the kind of subtle behavioral contract that's easy to silently break in later refactors and easy to pin down now with a single regression test.

Prompt: How would user time-sharing be simulated in this sytem to ensure that each user has the illusion of a consistent isolated environment while using the system?

NLS ran on a genuinely time-shared mainframe (an SDS 940), so each user's "consistent isolated environment" was actually an illusion constructed by the OS scheduler interleaving CPU slices across terminals. In your Clojure server, the JVM and Clojure's concurrency primitives already give you most of that illusion for free at the language level — the interesting design work is making sure isolation holds at the *data* and *resource* level too, and then proving it under concurrent load.

## 1. What "isolation" actually means here, decomposed

Worth separating into distinct guarantees, since each needs a different mechanism:

**State isolation** — one user's edits never bleed into another's session or document. **Fairness** — no single connection can starve others of CPU/IO (a flood of chord events from user A shouldn't lag user B's keystrokes). **Consistency under concurrency** — if two sessions for the *same* account (e.g. two terminals) touch the same document, the Journal must serialize those writes without corruption. **Temporal illusion** — each user perceives the system as responsive and theirs alone, even though the underlying execution is interleaved.

## 2. State isolation: per-session, per-account boundaries

This part is mostly architectural, and largely already implied by earlier design choices, but worth making explicit and testable:

```clojure
(ns nls.isolation)

;; Each connection owns its own atom — no shared mutable state between sessions.
(defn new-session [account-id conn]
  (atom {:account-id account-id
         :conn conn
         :cursor nil
         :input {:button-state 0}
         :designation nil}))

;; The registry mapping connections to sessions is the ONLY shared mutable
;; structure, and it only ever holds opaque session atoms, never lets one
;; session reach into another's.
(defonce sessions (atom {}))

(defn register-session! [conn-id session]
  (swap! sessions assoc conn-id session))
```

The key invariant to test: **no code path ever takes a `conn-id` from one session and uses it to read or mutate another session's atom directly.** All cross-session interaction (if any — e.g. shared documents) must go through the Journal, never through direct atom access. This is testable as a static/structural property — grep for any function that takes two session atoms as arguments — but also as a runtime property:

```clojure
(deftest sessions-are-mutually-opaque
  (let [s1 (new-session :alice conn1)
        s2 (new-session :bob conn2)]
    (handle-event s1 chord-event)
    (is (= {:account-id :bob :cursor nil :designation nil}
           (select-keys @s2 [:account-id :cursor :designation]))
        "activity on s1 must not perturb s2")))
```

## 3. Simulating the scheduler: round-robin event dispatch

Rather than letting the OS/JVM thread scheduler be the only thing producing the time-sharing illusion (which is realistic but non-deterministic and hard to test), it's worth building an explicit, simulate-able scheduler layer — this is actually closer to how NLS's own front-end multiplexer worked, and it gives you a deterministic harness for testing fairness:

```clojure
(ns nls.scheduler
  (:require [clojure.core.async :as a]))

;; Each session has its own inbound event channel; a single dispatcher
;; loop round-robins across all active sessions' channels, giving each
;; a bounded "time slice" (here: process up to N queued events) before
;; moving on — analogous to a scheduler quantum.
(defn make-dispatcher [quantum]
  (let [session-chans (atom {})]
    {:register! (fn [conn-id ch] (swap! session-chans assoc conn-id ch))
     :unregister! (fn [conn-id] (swap! session-chans dissoc conn-id))
     :run-loop
     (fn []
       (a/go-loop []
         (doseq [[conn-id ch] @session-chans]
           (loop [n 0]
             (when (< n quantum)
               (when-let [event (a/poll! ch)]
                 (process-event! conn-id event)
                 (recur (inc n))))))
         (a/<! (a/timeout 5))   ;; yield, mirrors a scheduler tick
         (recur)))}))
```

This makes the time-sharing behavior an explicit, swappable strategy rather than an emergent accident of thread scheduling — which matters because it means you can test fairness deterministically (feed N events into two channels, assert they get interleaved roughly evenly) rather than relying on flaky timing-based assertions against real OS threads.

An alternative, equally valid for a JVM server, is to just let each connection run on its own thread/`go` block and rely on `core.async`'s fair channel semantics plus the JVM scheduler — simpler, and realistic, but harder to write deterministic tests against. I'd suggest building the explicit dispatcher specifically *for the test suite*, even if production uses plain per-connection threads, so you get a controllable model of "the illusion of time-sharing" to assert against.

## 4. Testing fairness with simulated concurrent load

```clojure
(deftest round-robin-fairness
  (let [results (atom [])
        dispatcher (make-dispatcher 1)  ;; quantum of 1 event per session per tick
        ch-a (a/chan 100) ch-b (a/chan 100)]
    ((:register! dispatcher) :alice ch-a)
    ((:register! dispatcher) :bob ch-b)
    ;; Alice floods 50 events; Bob sends 1.
    (dotimes [i 50] (a/>!! ch-a {:user :alice :seq i}))
    (a/>!! ch-b {:user :bob :seq 0})
    (run-dispatcher-for-n-ticks! dispatcher 5)
    ;; Bob's single event must be processed promptly, not stuck behind
    ;; all 50 of Alice's — this is the actual claim "time-sharing" makes.
    (is (some #(= :bob (:user %)) (take 3 @results))
        "a flood from one user must not starve another's first event")))
```

This is the test that actually validates the thing you asked about: not "does each session have its own atom" (a structural fact) but "does a heavy user degrade a light user's experience" (a *behavioral* fairness claim), which is the actual illusion NLS's scheduler was preserving.

## 5. Concurrency at the Journal layer

Per-account isolation handles most cases, but if you ever allow two connections under the same account (two terminals, or a future multi-user shared-document feature), the Journal needs explicit serialization per document, since two concurrent saves racing on the same `doc-id` is the one place where "isolation" genuinely can't mean "totally independent" — they're touching the same resource.

```clojure
;; One agent per doc-id serializes all writes to that document,
;; regardless of which session initiated them.
(defonce doc-agents (atom {}))

(defn doc-agent [doc-id]
  (-> doc-agents
      (swap! update doc-id #(or % (agent nil)))
      (get doc-id)))

(defn save! [account doc-id new-tree]
  (send (doc-agent doc-id)
        (fn [_] (journal/write-version! account doc-id new-tree))))
```

Agents give you exactly the serialization semantics you want here: sends queue up and execute one-at-a-time per agent, so concurrent saves to the same document are naturally linearized without you writing any locking code — and it's straightforward to test by hammering `save!` concurrently from multiple threads and asserting the resulting version chain is a valid, non-corrupted sequence.

```clojure
(deftest concurrent-saves-are-serialized-not-corrupted
  (let [doc-id (random-doc-id)]
    (->> (range 20)
         (map (fn [i] (future (save! :alice doc-id (tree-with-marker i)))))
         doall
         (run! deref))
    (let [versions (journal/versions :alice doc-id)]
      (is (= 20 (count versions)))
      (is (apply distinct? (map :hash versions))
          "no version should silently overwrite another"))))
```

## 6. The "illusion of responsiveness" — latency budget testing

The other half of the time-sharing illusion NLS had to maintain was perceived responsiveness — a user typing shouldn't feel the system "thinking about someone else." Worth adding a latency-budget test at the dispatcher level:

```clojure
(deftest interactive-latency-under-load
  (let [dispatcher (make-dispatcher 5)
        light-ch (a/chan 10)
        heavy-chs (repeatedly 20 #(a/chan 1000))]
    (doseq [ch heavy-chs] (dotimes [i 1000] (a/>!! ch {:seq i})))
    (let [start (System/currentTimeMillis)]
      (a/>!! light-ch {:user :light :seq 0})
      (run-dispatcher-until #(processed? :light 0))
      (is (< (- (System/currentTimeMillis) start) 50)
          "a single light user's event must be served within budget even with 20 heavy sessions active"))))
```

This kind of test encodes the actual requirement you're asking about as a number — a response-time SLA per session regardless of total system load — rather than leaving "illusion of isolation" as a qualitative goal you can't verify mechanically.

---

**Summary of the layering:** structural isolation (separate atoms/namespaces per session — cheap, mostly a discipline you enforce via code review and the "mutual opacity" test) sits underneath a scheduling/fairness layer (round-robin dispatcher, testable deterministically) which sits underneath resource-contention handling for the rare shared-resource case (per-document agents, testable via concurrent-save races). Each layer has a different *kind* of test — structural assertion, deterministic interleaving check, and concurrent stress test, respectively — and you'd want all three in the suite, since each one catches a different way the "consistent isolated environment" illusion could leak.

Prompt: How can the system allow 2 users to have a co-editing session on the same document at the same time?

Co-editing changes the model from "one agent serializes writes to a document" (last answer) to "multiple sessions concurrently mutate a shared live document and need to see each other's changes in near-real-time." That's a different problem — not just write-serialization, but conflict resolution, change propagation, and presence (where's the other person's cursor). Worth walking through each piece.

## 1. Shared document state: from per-session tree to a shared mutable reference

Right now each session has its own zipper into a copy of the tree. For co-editing, the document itself needs to become a shared, mutable point of truth that multiple sessions attach to, while each session still keeps its own *view* state (cursor position, viewspec, designation) independently.

```clojure
(ns nls.coedit)

;; One shared atom per actively co-edited document, holding the
;; canonical current tree plus an editing-event log for this session.
(defrecord SharedDoc [tree-atom        ;; current outline tree
                      subscribers      ;; map of conn-id -> response channel
                      op-log           ;; vector of applied operations, for replay/audit
                      version-base])   ;; the Journal version this doc was loaded from

(defonce open-docs (atom {}))  ;; doc-id -> SharedDoc

(defn open-shared-doc! [doc-id account]
  (or (get @open-docs doc-id)
      (let [doc (->SharedDoc (atom (journal/load-latest account doc-id))
                              (atom {})
                              (atom [])
                              (journal/latest-version account doc-id))]
        (swap! open-docs assoc doc-id doc)
        doc)))

(defn join! [doc-id conn-id response-chan]
  (swap! (:subscribers (get @open-docs doc-id)) assoc conn-id response-chan))
```

Each session keeps a *separate* cursor/viewspec, but both point at the same `tree-atom`. This is the structural shift: document state goes from session-owned to doc-owned, with sessions as observers/mutators of it.

## 2. The conflict problem, and why CRDT-style operations fit well here

Two users editing the same outline concurrently will produce conflicting edits — both renaming the same node, one deleting a node the other just indented, etc. There are two broad strategies:

**Locking (subtree-level, NLS-plausible)**: a user "claims" a subtree (similar to designation, but exclusive) before editing it; other users can view but not edit that subtree until released. This is simple to reason about and arguably matches NLS's era better than fine-grained merge algorithms, which weren't common yet — and it sidesteps the hardest distributed-systems problems.

**Operation-based merging (CRDT/OT-style)**: every edit is expressed as a small operation (insert-node, move-node, set-text) tagged with a position identifier that survives concurrent edits; operations from different users are merged deterministically. More complex, but allows true simultaneous fine-grained editing without lockout.

Given the outline-tree structure (not flat text), I'd recommend a middle path: **node-level optimistic locking with operation logging**, which is much simpler than full CRDT outline merging but still allows two people to work in different parts of the same document freely.

```clojure
(defrecord Operation [op-id        ;; unique, e.g. [conn-id local-seq]
                       node-path    ;; path to the node, by stable node-id not index
                       kind         ;; :set-text :insert-child :delete :move :indent :outdent
                       payload
                       base-version]) ;; version of the node the editor last saw

(defn apply-op! [shared-doc op]
  (let [{:keys [tree-atom op-log]} shared-doc]
    (swap! tree-atom
           (fn [tree]
             (if (compatible? tree op)
               (perform op tree)
               (raise-conflict op tree))))   ;; see step 3
    (swap! op-log conj op)))
```

The crucial property: every node carries a **stable node-id** (a UUID assigned at creation, never recycled), not a tree-path index — paths shift under concurrent edits, but IDs don't. This is what makes `compatible?` checks tractable: an operation targeting node-id `N` with `base-version` `V` is safe to apply if node `N`'s current version still matches `V`; if another op already changed it, you have a real conflict to resolve rather than silent corruption.

## 3. Conflict resolution policy

When `compatible?` fails, you need a deterministic rule, not ad hoc handling:

```clojure
(defn resolve-conflict [op current-node]
  (case (:kind op)
    ;; Text edits: last-writer-wins is acceptable for short outline labels —
    ;; flag to the loser that their version was superseded, let them retry
    ;; against the new base, rather than silently dropping or silently overwriting.
    :set-text {:resolution :reject-retry :current current-node}

    ;; Structural ops (move/delete) on a node someone else just deleted:
    ;; surface as an explicit conflict notification rather than resolving silently.
    (:move :delete :indent) {:resolution :conflict :reason :node-mutated-concurrently}))
```

The important design decision to make explicit (and document for users): **outline structure conflicts are surfaced, not silently merged**; only plain text-field edits get last-writer-wins, because silently merging structural moves on a hierarchical outline can produce a tree that neither user intended. This is a defensible, simple policy — more sophisticated merge logic can be layered in later if it proves too restrictive in practice.

## 4. Propagating changes to the other session(s)

Once an operation applies successfully, every other subscriber to that doc needs to see it — this is the "co-" part of co-editing:

```clojure
(defn broadcast-op! [shared-doc op origin-conn-id]
  (doseq [[conn-id ch] @(:subscribers shared-doc)]
    (when (not= conn-id origin-conn-id)
      (a/put! ch (encode-response :outline/op-applied op)))))
```

This is where the protocol from earlier needs a new response frame type — `0x85 outline-op-broadcast` — distinct from the per-command response sent back to the originating session, since the *other* session receives this asynchronously, not as a reply to anything it sent.

## 5. Presence: showing each user's cursor/designation to the other

Part of the co-editing illusion is seeing where your collaborator is — NLS-era systems didn't really have this (no concept of a second live cursor on screen), but a modern co-editing session should. This is comparatively simple: broadcast cursor/designation changes the same way as edit ops, but as ephemeral presence events that aren't journaled:

```clojure
(defn broadcast-presence! [shared-doc conn-id presence]
  (doseq [[other-id ch] @(:subscribers shared-doc)]
    (when (not= other-id conn-id)
      (a/put! ch (encode-response :presence/update {:user conn-id :at presence})))))
```

Keep presence updates explicitly out of `op-log` — they're not part of document history and shouldn't ever be journaled or replayed; conflating "where is your cursor" with "what changed in the document" is a common source of bugs in collaborative editors.

## 6. Integration with the Journal

The shared live document is a working copy; the Journal's append-only versioning from earlier still applies, just triggered differently — periodic auto-checkpoint or explicit save, snapshotting the *merged* state rather than either user's individual edits:

```clojure
(defn checkpoint! [shared-doc account doc-id]
  (journal/save! account doc-id @(:tree-atom shared-doc)))

;; e.g. checkpoint on every Nth operation, or every K seconds, or on explicit save chord
```

Worth deciding explicitly: does a checkpoint record *who* contributed which parts? If so, the Journal's version metadata needs to track multiple authors per version (a list, not a single `:author` field) — a small but easy-to-miss schema change once co-editing exists.

## 7. Testing strategy

This is the layer where testing matters most, because the bug class here — race conditions in concurrent edits — is exactly the kind that won't show up in single-threaded manual testing.

**Deterministic conflict tests** (no real concurrency, just sequenced ops):

```clojure
(deftest concurrent-text-edit-last-writer-wins
  (let [doc (open-shared-doc! "doc1" :alice)
        node-id (first-child-id @(:tree-atom doc))
        base-v (node-version @(:tree-atom doc) node-id)]
    (apply-op! doc (->Operation [:alice 0] node-id :set-text "hello" base-v))
    (let [result (apply-op! doc (->Operation [:bob 0] node-id :set-text "world" base-v))]
      (is (= :reject-retry (:resolution result))
          "second concurrent text edit on stale base must be flagged, not silently applied"))))

(deftest non-overlapping-edits-both-succeed
  (let [doc (open-shared-doc! "doc1" :alice)
        [n1 n2] (two-sibling-node-ids @(:tree-atom doc))]
    (apply-op! doc (->Operation [:alice 0] n1 :set-text "a" (node-version @(:tree-atom doc) n1)))
    (apply-op! doc (->Operation [:bob 0]   n2 :set-text "b" (node-version @(:tree-atom doc) n2)))
    (is (= "a" (text-of @(:tree-atom doc) n1)))
    (is (= "b" (text-of @(:tree-atom doc) n2))
        "edits to different nodes must both succeed without interference")))
```

**Stress/race test** with real concurrency, asserting on invariants rather than exact outcomes (since interleaving order is nondeterministic by design):

```clojure
(deftest concurrent-stress-no-corruption
  (let [doc (open-shared-doc! "stress-doc" :alice)
        node-ids (all-node-ids @(:tree-atom doc))]
    (->> (for [i (range 200)]
           (future (apply-op! doc (random-valid-op node-ids))))
         doall (run! deref))
    (is (valid-tree? @(:tree-atom doc))
        "tree must remain structurally valid after 200 concurrent ops")
    (is (= (count (op-log doc)) (count (distinct (op-log doc))))
        "no operation should be double-applied")))
```

**Property-based test for the merge invariant** — this is the strongest guarantee worth investing in: pick any two sequences of non-conflicting operations and assert that applying them in either interleaved order produces the same resulting tree (a basic confluence property), using `test.check` to generate random op sequences against random small trees rather than hand-picking a few cases.

**Broadcast/integration test**: spin up two simulated sessions against one `open-shared-doc!`, have session A apply an edit, assert session B's channel receives the corresponding `outline/op-applied` frame within a latency budget — this is the test that validates the actual "co-" experience end-to-end, distinct from the conflict-resolution unit tests above.

---

The overall shift from the single-user model: documents move from being session-private to being a shared, identity-stable (node-IDs, not paths) structure with an explicit, conservative conflict policy (structural conflicts surfaced, not merged); the Journal becomes a periodic checkpoint of merged state rather than a 1:1 record of one user's saves; and a new presence-broadcast channel handles the "see your collaborator" illusion separately from the document-mutation channel. The trade-off worth flagging to whoever's deciding scope: full real-time character-level co-editing (like Google Docs) is a much bigger lift than node-level optimistic locking with conflict surfacing — I'd push for the latter as a first version unless there's a strong reason to need finer granularity, since it keeps the conflict-resolution logic small enough to actually verify with the tests above.

Prompt: How can an editing session by one user be broadcast to multiple users to simulate the groupware environment that was used by Engelbart's team?

Engelbart's team used NLS not just for concurrent editing but for shared-viewing/presentation scenarios — the famous "Mother of All Demos" itself was a broadcast session where Engelbart's actions (cursor moves, viewspec changes, screen contents) were pushed out to remote viewers in Menlo Park. That's a distinct use case from the peer co-editing in the last answer: here there's typically one active "driver" and N passive (or semi-passive) observers, and what's being broadcast is often *more* than document edits — it's view-state, scroll position, even raw screen deltas.

Worth modeling this as its own layer on top of what's already built, since it has different semantics: a **group/room** concept, a **driver/follower** distinction, and a broader broadcast surface (view-state, not just operations).

## 1. Group sessions as a first-class concept

```clojure
(ns nls.groupware)

(defrecord GroupSession [group-id
                          doc-id
                          driver-conn       ;; the conn-id currently "presenting" (nil = free-for-all)
                          members           ;; map of conn-id -> {:role :driver/:follower, :chan ...}
                          mode])            ;; :locked-follow | :free-roam | :co-edit

(defonce groups (atom {}))

(defn create-group! [group-id doc-id driver-conn]
  (swap! groups assoc group-id
         (->GroupSession group-id doc-id driver-conn
                         {driver-conn {:role :driver}}
                         :locked-follow)))

(defn join-group! [group-id conn-id chan]
  (swap! groups update-in [group-id :members]
         assoc conn-id {:role :follower :chan chan}))
```

The `mode` field is the key extensibility point: `:locked-follow` means followers' viewports are forced to match the driver's (the Mother of All Demos scenario — remote viewers see exactly what Engelbart sees); `:free-roam` means members can independently navigate the same doc while still seeing each other's edits/presence (closer to the co-editing case from the last answer); `:co-edit` layers in the conflict-resolution machinery from before. This makes "groupware" a spectrum rather than one fixed behavior, which matches how NLS's own collaborative features evolved over time.

## 2. What gets broadcast — beyond just edit operations

The earlier `broadcast-op!` only sent document mutations. A presentation/groupware session needs to broadcast **view-state**, since followers in `:locked-follow` mode need to see the driver's scroll position, expand/collapse state, and viewspec changes too — none of which mutate the document itself.

```clojure
(defn broadcast-view-state! [group-id conn-id view-state]
  (let [group (get @groups group-id)]
    (when (= conn-id (:driver-conn group))   ;; only driver's view propagates in locked mode
      (doseq [[member-id {:keys [chan role]}] (:members group)]
        (when (and (not= member-id conn-id) (= :follower role))
          (a/put! chan (encode-response :group/view-sync
                                          {:cursor (:cursor view-state)
                                           :viewspec (:viewspec view-state)
                                           :scroll (:scroll view-state)})))))))
```

This needs a new response frame distinct from `outline/op-applied` — call it `0x86 view-sync` — since followers must apply it to their *own* render state without it being mistaken for a document edit (it shouldn't go through conflict resolution or the op-log at all).

## 3. Unifying the broadcast path

Both document operations and view-state changes funnel through the same per-group fan-out, just to different subsets of members and via different frame types — worth factoring as one dispatch point so adding new broadcastable event types later (e.g. a "pointer flash" highlight, similar to gestures NLS operators used) doesn't require new plumbing each time:

```clojure
(defn broadcast! [group-id origin-conn-id frame-type payload {:keys [drivers-only? exclude-origin?]
                                                                :or {exclude-origin? true}}]
  (let [group (get @groups group-id)]
    (doseq [[member-id {:keys [chan role]}] (:members group)]
      (when (and (or (not exclude-origin?) (not= member-id origin-conn-id))
                 (or (not drivers-only?) (= role :driver) (not= member-id (:driver-conn group))))
        (a/put! chan (encode-response frame-type payload))))))
```

Then the two call sites collapse to:

```clojure
;; document mutation, co-edit mode, all peers
(broadcast! group-id conn-id :outline/op-applied op {})

;; driver's view, locked-follow mode, followers only
(when (driver? group-id conn-id)
  (broadcast! group-id conn-id :group/view-sync view-state {}))
```

## 4. Driver handoff and role changes

A real groupware session needs the ability to change who's driving — e.g. Engelbart handing control to a colleague mid-demo:

```clojure
(defn transfer-driver! [group-id from-conn to-conn]
  (swap! groups update group-id
         (fn [g]
           (-> g
               (assoc :driver-conn to-conn)
               (assoc-in [:members from-conn :role] :follower)
               (assoc-in [:members to-conn :role] :driver))))
  (broadcast! group-id from-conn :group/driver-changed {:new-driver to-conn} {:exclude-origin? false}))
```

This should be its own explicit command (mapped to a chord or control frame), not implicit — ambiguity about who currently has control is exactly the kind of thing that turns a live demo into chaos, so the protocol should make a driver-change an unambiguous, broadcast, acknowledged event.

## 5. Late joiners need current state, not just future deltas

Anyone joining a group session mid-stream needs a snapshot to render before they start receiving incremental `view-sync`/`op-applied` frames — otherwise they're applying deltas to state they never had:

```clojure
(defn join-group! [group-id conn-id chan]
  (let [group (get @groups group-id)
        doc (open-shared-doc! (:doc-id group) nil)]
    (a/put! chan (encode-response :group/snapshot
                                    {:tree @(:tree-atom doc)
                                     :driver-view (current-view-state (:driver-conn group))}))
    (swap! groups update-in [group-id :members] assoc conn-id {:role :follower :chan chan})))
```

This ordering matters: write the snapshot to the channel *before* registering the member as a broadcast recipient, or there's a race where a `view-sync` could arrive and get applied before the snapshot it depends on.

## 6. Testing strategy

**Fan-out correctness** — does everyone in the right role-subset get the message, and no one else:

```clojure
(deftest locked-follow-broadcasts-only-to-followers
  (let [g (test-group :locked-follow :driver :alice :followers [:bob :carol])]
    (broadcast-view-state! (:id g) :alice {:scroll 42})
    (is (received? :bob :group/view-sync))
    (is (received? :carol :group/view-sync))
    (is (not (sent-anything? :alice)) "origin shouldn't receive its own broadcast")))

(deftest non-driver-view-changes-dont-propagate-in-locked-mode
  (let [g (test-group :locked-follow :driver :alice :followers [:bob])]
    (broadcast-view-state! (:id g) :bob {:scroll 99})  ;; bob isn't driver
    (is (not (received? :alice :group/view-sync))
        "only the driver's view-state should ever broadcast in locked-follow mode")))
```

**Driver handoff correctness**:

```clojure
(deftest driver-transfer-updates-roles-and-notifies-all
  (let [g (test-group :locked-follow :driver :alice :followers [:bob])]
    (transfer-driver! (:id g) :alice :bob)
    (is (= :bob (:driver-conn (get @groups (:id g)))))
    (is (received? :alice :group/driver-changed))
    (is (received? :bob :group/driver-changed))))
```

**Late-join snapshot consistency** — the race condition flagged above is exactly the kind of thing to pin with a regression test:

```clojure
(deftest late-joiner-receives-snapshot-before-any-delta
  (let [g (test-group :locked-follow :driver :alice :followers [])
        events (atom [])
        carol-chan (capturing-chan events)]
    (join-group! (:id g) :carol carol-chan)
    (broadcast-view-state! (:id g) :alice {:scroll 7})
    (is (= :group/snapshot (:type (first @events)))
        "snapshot must always be the first frame a late joiner receives")))
```

**Scale/fan-out load test** — since a real groupware demo (per the Mother of All Demos scenario) might have many passive followers watching one driver, worth a test asserting broadcast latency doesn't degrade meaningfully as follower count grows:

```clojure
(deftest broadcast-latency-scales-with-followers
  (doseq [n [1 10 50]]
    (let [g (test-group :locked-follow :driver :alice :followers (gen-followers n))
          elapsed (time-broadcast (:id g) :alice {:scroll 1})]
      (is (< elapsed 20) (str "broadcast to " n " followers exceeded latency budget")))))
```

---

The conceptual addition over the previous co-editing answer: groupware introduces a **group/role structure** (driver vs. follower, with switchable modes) and a **broader broadcast surface** (view-state and presence, not just document mutations), plus the operational concerns specific to presentation scenarios — driver handoff and late-joiner snapshotting — that don't arise in peer-to-peer co-editing. If it'd help, a natural next step would be sketching how `:free-roam` and `:co-edit` modes interoperate within the same group (e.g. a demo where most people are just watching but two collaborators are actively editing alongside the driver), since that's closer to how Engelbart's actual NLS sessions sometimes mixed presentation and live collaborative work.

Prompt: How would the architecture change to include functionality for users to draw point-to-point line graphics similar to the one in Engelbart's 1968 demo showing the stores he would visit on his way home?  Assume that the Quil library would be used to create these graphics.  The demo also showed how each point could be labelled and associated with a specific statement in an outline.

Quil is a wrapper around Processing, which expects to own a window/canvas and run a draw loop — that's a different execution model than the headless byte-stream server you've been building. So the first architectural decision is *where* Quil actually runs, and that shapes everything else.

## 0. Where does Quil fit — server-side render vs. client-side companion

Two viable options:

**(a) Server-side offscreen rendering.** Quil can run headlessly using `:renderer :p2d` or `:none` with an offscreen `PGraphics` buffer, producing PNG/raw pixel bytes without ever opening a window. The server renders the graphic on demand and ships pixel data (or an image frame) back over the byte stream as a new response frame type. This keeps your "single binary protocol, dumb client" model intact — consistent with everything built so far — at the cost of the server doing rendering work and pushing image bytes rather than vector data.

**(b) Server sends vector data; a Quil-based client renders it.** The server stays purely about outline/graphics *data* — points, lines, labels, associations — and a separate client application (which could itself be a Quil sketch) receives that data over the byte stream and draws it locally. This is more in the spirit of the rest of your architecture (server reasons about model, client renders), and is probably the better fit, since it avoids putting a stateful rendering library inside your core server loop.

I'd recommend **(b)** as the primary design, with **(a)** kept available as an optional "render and snapshot" capability — e.g., for generating a static image to attach to a Journal version or to support a thin/non-Quil client. I'll design for both, but data-first.

## 1. Domain model: a new artifact type alongside the outline

The 1968 demo's "route map" is a distinct artifact type — a set of labeled points connected by lines, where each point optionally links back to an outline node. This shouldn't be bolted onto the outline data structure; it's a sibling document type that *references* outline nodes.

```clojure
(ns nls.graphics)

(defrecord Point [id          ;; stable UUID, like outline node-ids
                   x y         ;; canvas coordinates
                   label       ;; display text
                   node-ref])  ;; optional outline node-id this point is linked to

(defrecord LineSeg [id from-point-id to-point-id])

(defrecord RouteGraphic [id
                          points    ;; map of point-id -> Point
                          lines     ;; map of line-id -> LineSeg
                          doc-ref]) ;; the OPML doc-id this graphic is associated with
```

The `node-ref` on `Point` is the actual feature you're asking about — "each point could be labelled and associated with a specific statement in an outline" — modeled as a foreign-key-style reference, exactly like `node-id` was used for stable addressing in the co-editing design. This means a point's *label* can either be free text or, when linked, derived from (or kept in sync with) the referenced outline node's text.

```clojure
(defn point-display-text [graphic point-id outline-tree]
  (let [p (get-in graphic [:points point-id])]
    (if-let [node-id (:node-ref p)]
      (outline/text-of outline-tree node-id)   ;; live-linked: always reflects current outline text
      (:label p))))                            ;; freestanding label
```

Worth deciding explicitly whether linked labels are *live* (always shows current outline text, as above) or *snapshotted* (copied at link-creation time, edited independently thereafter) — live is more powerful and more in keeping with NLS's link philosophy, but means a graphic's rendering depends on the outline's current state, which has implications for the Journal (next section).

## 2. Protocol extensions

New frame types, both directions:

```
Client → Server (commands):
  0x05  graphics/add-point    {x, y, label?, node-ref?}
  0x06  graphics/add-line     {from-point-id, to-point-id}
  0x07  graphics/move-point   {point-id, x, y}
  0x08  graphics/link-point    {point-id, node-id}   ;; associate existing point with outline statement
  0x09  graphics/select-point  {point-id}            ;; e.g. clicking a point jumps outline cursor to linked node

Server → Client (responses):
  0x87  graphics/snapshot      full RouteGraphic state, on open
  0x88  graphics/delta         single point/line add/move, for broadcast to co-viewers
  0x89  graphics/render-image  optional: PNG bytes, if server-side Quil rendering (option a) is used
```

`graphics/select-point` is the direct analog of the demo's interactive behavior — clicking a point on the map should move the outline cursor to (and ideally scroll/highlight) the associated statement, the same way Engelbart's system tied spatial and textual representations of the same information together.

```clojure
(defn handle-select-point [session graphic-id point-id]
  (when-let [node-id (:node-ref (get-in (get-graphic graphic-id) [:points point-id]))]
    (swap! session update :cursor outline/move-to-node node-id)
    (emit! session :outline/cursor-moved {:node-id node-id})))
```

This is the cross-link in the other direction too: outline navigation could optionally highlight an associated point on the graphic, if one exists — worth exposing as a lookup index (`node-id -> point-ids`) maintained alongside the graphic, rather than scanning all points on every cursor move.

## 3. Mouse-driven point placement, reusing the designation mechanism

You already have a "bug" designation latch from the chord-keyset design. Drawing a point is naturally: move mouse, click designate-button to register the location, then a chord/command says "place a labeled point here, linked to the currently-designated outline node" — which directly mirrors how NLS combined mouse designation with chord commands generally:

```clojure
(defcommand place-linked-point 23 [session]
  (let [{:keys [x y]} (current-designation session)
        node-id (:node-ref (current-designation session))]  ;; if designation came from outline view
    (graphics/add-point! (active-graphic session)
                          {:x x :y y
                           :label (outline/text-of (current-tree session) node-id)
                           :node-ref node-id})))
```

This reuses, rather than duplicates, the designation/chord machinery from earlier — the graphics feature becomes another *consumer* of the existing input model, not a parallel input path.

## 4. Storage and the Journal

`RouteGraphic` is a new persisted document type alongside OPML. Two reasonable approaches:

**Separate journal stream**: store graphics as their own versioned artifact (e.g. `.graphic.edn` files) in the account directory, journaled the same way as OPML docs — same `journal/save!`/`journal/versions` API, generalized to take a serializer per document type (this is exactly the `server.format` extensibility point flagged back in the original project plan).

```clojure
(defmulti serialize-doc :doc-type)
(defmethod serialize-doc :opml [doc] (opml/render doc))
(defmethod serialize-doc :route-graphic [doc] (pr-str doc))   ;; or a small custom EDN/XML schema
```

**Versioning interaction with live-linked labels**: if labels are live-linked (per the decision in section 1), then a graphic's *meaning* can change even when the graphic itself isn't edited, purely because the linked outline node's text changed underneath it. Worth deciding: does saving a new OPML version also implicitly create a new graphic version (to keep them paired), or does the graphic just always resolve against "whatever the current OPML version is," with no separate versioning at all? I'd lean toward the latter for simplicity — keep graphics referencing nodes by stable ID, resolved against current document state at render time — and only introduce graphic-specific versioning if users need to snapshot "the map as it looked when I drew it," independent of subsequent outline edits.

## 5. Quil rendering (client side, or optional server-side snapshot)

```clojure
(ns nls.client.render
  (:require [quil.core :as q]))

(defn draw-graphic [graphic]
  (q/background 255)
  (doseq [{:keys [from-point-id to-point-id]} (vals (:lines graphic))]
    (let [p1 (get-in graphic [:points from-point-id])
          p2 (get-in graphic [:points to-point-id])]
      (q/line (:x p1) (:y p1) (:x p2) (:y p2))))
  (doseq [{:keys [x y label]} (vals (:points graphic))]
    (q/ellipse x y 8 8)
    (q/text label (+ x 10) y)))

(defn sketch [graphic-state-atom]
  (q/sketch
    :draw (fn [] (draw-graphic @graphic-state-atom))
    :setup (fn [] (q/frame-rate 30))))
```

The `graphic-state-atom` here is fed by incoming `graphics/snapshot` and `graphics/delta` frames from the server — same client-side update pattern you'd use for `view-sync`/`op-applied` in the groupware design, just a different data shape. If broadcasting a drawing session to multiple viewers (extending the groupware model from the previous answer), `graphics/delta` frames fan out through the exact same group/broadcast machinery — a route-graphic edit is just another event type alongside `outline/op-applied` and `group/view-sync`, requiring no new fan-out logic, only a new frame type in the existing `broadcast!` dispatch.

For optional server-side snapshotting (option a, e.g. to embed a static image in a saved Journal version or serve a non-Quil thin client): run Quil headless against an offscreen buffer and emit PNG bytes.

```clojure
(ns nls.server.render
  (:require [quil.core :as q]))

(defn render-to-png-bytes [graphic width height]
  (let [buf (q/create-graphics width height :p2d)]
    (q/with-graphics buf
      (draw-graphic graphic))
    (-> buf .toImage png-bytes-of)))   ;; pseudo; actual impl via ImageIO
```

## 6. Testing strategy

**Pure data-model tests** (point/line/label CRUD, node-ref resolution):

```clojure
(deftest linked-label-tracks-outline-text
  (let [tree (outline/text-set (sample-tree) :node/1 "Grocery store")
        g (-> (empty-graphic) (add-point :p1 {:x 0 :y 0 :node-ref :node/1}))]
    (is (= "Grocery store" (point-display-text g :p1 tree)))
    (let [tree2 (outline/text-set tree :node/1 "Hardware store")]
      (is (= "Hardware store" (point-display-text g :p1 tree2))
          "live-linked label must reflect current outline text without graphic edit"))))
```

**Cross-link navigation test** (the key interactive feature):

```clojure
(deftest selecting-point-moves-outline-cursor
  (let [session (test-session)
        g (graphic-with-linked-point :p1 :node/42)]
    (handle-select-point session (:id g) :p1)
    (is (= :node/42 (:node-id (:cursor @session))))))
```

**Broadcast integration test**, reusing the groupware harness from before:

```clojure
(deftest graphic-delta-broadcasts-to-group
  (let [g (test-group :free-roam :driver :alice :followers [:bob])]
    (place-point! (:doc-id g) :alice {:x 10 :y 20 :label "Bank"})
    (is (received? :bob :graphics/delta))))
```

**Render smoke test** (headless Quil, just verifying it doesn't throw and produces non-trivial output):

```clojure
(deftest headless-render-produces-image
  (let [bytes (render-to-png-bytes (sample-graphic) 400 300)]
    (is (> (count bytes) 1000) "rendered PNG should be non-trivially sized")))
```

---

The core architectural addition: a new sibling artifact type (`RouteGraphic`) with stable-ID cross-references into the outline, reusing existing infrastructure rather than duplicating it — the designation/chord input model for point placement, the Journal's pluggable-serializer mechanism for persistence, and the groupware broadcast layer for multi-viewer drawing sessions. The one genuinely new design decision is the live-link-vs-snapshot question for labels, which is worth pinning down early since it affects both the Journal versioning strategy and how aggressively the client needs to re-render when outline edits happen elsewhere.

Prompt: Think about the impact of building the NLS simulator in a local-first technology that uses decentralized data to replicate changes to peers.  What architectural considerations should be added for this requirement?

Local-first fundamentally inverts the trust topology of everything built so far. The design so far assumes a central server that is the authoritative source of truth — sessions attach to it, the Journal lives on it, broadcasts originate from it. Local-first means every peer is simultaneously a client, a server, and a replica: changes originate locally without network round-trips, the Journal is replicated across peers rather than held centrally, and "the server" becomes just another peer that may or may not be online at any given moment. That's not a feature addition — it's a different foundational assumption that propagates upward through nearly every layer already designed.

## 1. The core shift: from server-authoritative to CRDT-based shared state

The central question in any local-first design is: what is the merge rule when two peers have independently modified the same data? For the NLS system you have three distinct data types that need different answers.

**Outline trees** are the hardest. Plain last-writer-wins on a tree produces incoherent results — two peers independently moving the same node, or one deleting a subtree the other has expanded, need deterministic merge behavior that doesn't require a coordinating authority. The right tool here is a tree-CRDT, and the current practical options in the Clojure/JVM ecosystem are:

```clojure
;; Option A: Use automerge-clj (wraps the Automerge Rust library via JNI)
;; Automerge natively supports tree/map/list CRDTs and is designed for
;; exactly this use case — collaborative documents without a server.
(ns nls.crdt.outline
  (:require [automerge-clj.core :as am]))

(defn new-doc []
  (am/create))

(defn apply-change [doc change]
  (am/apply-changes doc [change]))

;; Changes are binary-serialized ops that can be exchanged peer-to-peer
;; and applied in any order; the CRDT ensures all peers converge.
(defn encode-change [doc prev-doc]
  (am/get-changes doc prev-doc))
```

**Option B** is to implement a simpler custom CRDT that fits the outline structure exactly — a log-structured sequence of operations tagged with vector clocks. This is more work but avoids the JNI dependency and gives you full control over conflict semantics. Given that your outline is already modeled as zipper operations over stable node-IDs, you are already partway there — the `Operation` records from the co-editing design map naturally onto CRDT ops if you add vector-clock tags.

```clojure
(defrecord Op [op-id         ;; [peer-id, logical-clock] — a Lamport timestamp
               node-id       ;; stable UUID — already in your model
               kind          ;; :set-text :insert :delete :move :indent :outdent
               payload
               parents])     ;; set of op-ids this op causally follows — the DAG structure

;; The operation log IS the document; the current tree is just a materialized view of it.
;; This is the same model used by Logoot, LSEQ, and Y.js for text;
;; adapted here for a tree rather than a linear sequence.
```

**Route graphics** are comparatively simple — points and lines are map entries keyed by stable UUIDs, so a grow-only set CRDT (G-Set) handles additions naturally, and moves/label-changes can be last-writer-wins per point since spatial edits rarely conflict semantically in the way that interleaved text edits do.

**Journal versions** are naturally append-only and immutable — they are already a CRDT (a grow-only log). Replication just means gossiping new version entries to peers; no conflict resolution needed since older versions are never mutated.

## 2. Vector clocks and causal ordering

Once you remove the central server as a sequencer, you lose the global ordering of events that you previously got for free from the server's serial dispatch. Replace it with vector clocks — one logical clock per peer, incremented on every local operation, piggybacked on every message:

```clojure
(ns nls.clock)

(defn new-clock [peer-id]
  {peer-id 0})

(defn tick [clock peer-id]
  (update clock peer-id (fnil inc 0)))

(defn merge-clocks [c1 c2]
  (merge-with max c1 c2))

(defn happens-before? [c1 c2]
  ;; c1 -> c2 iff every entry in c1 is <= the corresponding entry in c2
  ;; and at least one is strictly less.
  (and (every? (fn [[peer v]] (<= v (get c2 peer 0))) c1)
       (not= c1 c2)))

(defn concurrent? [c1 c2]
  (and (not (happens-before? c1 c2))
       (not (happens-before? c2 c1))))
```

Every `Op` record gets a `:clock` field, and the CRDT merge logic uses `concurrent?` to identify operations that need explicit conflict resolution (rather than simple causal ordering) — this replaces the `base-version` field from the co-editing design with a proper distributed causality mechanism:

```clojure
(defrecord Op [op-id
               node-id
               kind
               payload
               clock      ;; vector clock at time of creation
               peer-id])  ;; which peer originated this

(defn resolve-concurrent [op1 op2]
  ;; For text edits: deterministic tie-break by peer-id (arbitrary but consistent)
  ;; For structural ops: surface as explicit conflict (same policy as co-edit design,
  ;; but now triggered by concurrent? rather than stale base-version)
  (case [(:kind op1) (:kind op2)]
    [:set-text :set-text] (if (neg? (compare (:peer-id op1) (:peer-id op2))) op1 op2)
    :conflict))
```

## 3. Peer discovery and the replication transport

Without a central server, peers need to find each other. Options range in complexity:

```clojure
(ns nls.peer)

;; Each peer has a stable identity — a keypair, with the public key as peer-id.
;; This gives you identity without a central registry, and opens the door to
;; content-addressed storage and authenticated gossip later.
(defrecord Peer [peer-id       ;; public key, base58 encoded
                  private-key
                  known-peers   ;; atom: map of peer-id -> connection info
                  sync-state])  ;; atom: map of peer-id -> last-known vector clock for that peer

;; Discovery options (pick one or layer them):
;; 1. mDNS/Bonjour for LAN peers (good for Engelbart-style same-room groupware)
;; 2. A "bootstrap" peer list in config for known collaborators
;; 3. A DHT (e.g. BitTorrent-style) for fully decentralized discovery
;; 4. A lightweight "rendezvous" server — not authoritative, just introduces peers
;;    to each other's addresses, then steps aside. This is often the pragmatic
;;    compromise between "fully decentralized" and "actually works behind NAT".

(defn sync-with-peer! [local-peer remote-peer-id]
  ;; Anti-entropy gossip: exchange what each peer has that the other lacks
  (let [remote-clock (get-in @(:sync-state local-peer) [remote-peer-id :clock])
        missing-ops (ops-since (:op-log local-peer) remote-clock)]
    (send-to-peer remote-peer-id {:type :sync/ops :ops missing-ops :clock (current-clock local-peer)})))
```

For an NLS-inspired system used by a small team (like Engelbart's original group), mDNS + a shared bootstrap peer-list is probably the right pragmatic choice — fully-decentralized DHT is significant implementation overhead for a small-team tool, and a lightweight rendezvous server preserves local-first semantics (the rendezvous server has no document data, only addresses) while solving the NAT traversal problem practically.

## 4. The sync protocol: anti-entropy gossip

With no server serializing events, peers synchronize by periodically exchanging what they have. The standard approach is anti-entropy gossip with Merkle trees to efficiently find what each peer is missing:

```clojure
(ns nls.sync)

;; A Merkle DAG over the op log lets two peers quickly identify divergence
;; without shipping the full log every sync round.
(defn merkle-root [op-log]
  (->> op-log
       (map :op-id)
       sort
       (reduce hash-combine nil)))

(defn sync-round! [local-peer remote-peer]
  ;; Phase 1: exchange Merkle roots — if equal, already in sync.
  (let [local-root (merkle-root (get-local-ops local-peer))
        remote-root (request-merkle-root remote-peer)]
    (when (not= local-root remote-root)
      ;; Phase 2: binary search the op DAG to find the divergence point
      ;; Phase 3: exchange only the missing ops in both directions
      (let [missing-from-remote (ops-not-in remote-peer (get-local-ops local-peer))
            missing-from-local  (ops-not-in local-peer (get-remote-ops remote-peer))]
        (send-ops! remote-peer missing-from-remote)
        (receive-and-apply-ops! local-peer missing-from-local)))))
```

Sync rounds run as a background `core.async` loop per known peer, with exponential backoff when peers are unreachable — offline peers just accumulate in the backoff queue and sync automatically when they reappear.

## 5. How the Journal changes: from append-only-file to replicated op DAG

The Journal was previously a simple append-only log of document snapshots on the server's filesystem. In the local-first model it becomes a **replicated operation DAG** — every peer holds the full history, and "versions" are DAG nodes with causal parents rather than sequential version numbers:

```clojure
(ns nls.journal)

(defrecord Version [version-id   ;; hash of (parent-ids + tree-content)
                    parent-ids   ;; set of version-ids this was derived from — supports merges
                    tree-hash    ;; content-addressed hash of the tree at this version
                    author-peer
                    timestamp    ;; Lamport timestamp, not wall clock
                    op-range])   ;; the ops from parents to this version

;; A "save" creates a new DAG node whose parents are the current tips.
;; If two peers saved independently (a fork), their next shared save creates
;; a merge node — two parents — exactly like a Git merge commit.
(defn save! [local-peer doc-id]
  (let [current-tips (current-tips local-peer doc-id)
        new-version  (->Version (new-version-id)
                                 (set (map :version-id current-tips))
                                 (hash-tree (current-tree local-peer doc-id))
                                 (:peer-id local-peer)
                                 (tick-clock local-peer)
                                 (ops-since-tips local-peer doc-id current-tips))]
    (append-version! local-peer doc-id new-version)
    (broadcast-to-peers! local-peer :journal/new-version new-version)))
```

This is structurally identical to Git's DAG — which is not a coincidence, since Git is itself a local-first content-addressed version control system. The difference is that your Journal tracks outline/graphic documents and the ops that produced them, while Git tracks file bytes.

## 6. Identity, authentication, and trust without a central authority

The original design relied on the server to authenticate users. In a peer-to-peer system, identity needs to be self-sovereign:

```clojure
(ns nls.identity)

;; Peer identity is a keypair — the public key IS the peer-id.
;; Every op is signed by the originating peer, so receivers can verify
;; authorship without trusting a central authority.
(defn sign-op [op private-key]
  (assoc op :signature (crypto/sign (pr-str op) private-key)))

(defn verify-op [op]
  (crypto/verify (pr-str (dissoc op :signature))
                  (:signature op)
                  (peer-public-key (:peer-id op))))

;; Document access control: each doc has an ACL — a set of peer-ids
;; that are permitted to contribute ops. The creator signs the initial ACL;
;; new members can be added by any existing member with write permission.
(defrecord DocACL [doc-id
                    readers    ;; set of peer-ids
                    writers    ;; set of peer-ids
                    admins     ;; can modify ACL
                    acl-sig])  ;; signed by the admin who last modified it
```

For the NLS groupware use case (a small trusted team), a simple "known peer list with explicit invite" model is sufficient — each peer maintains a `trusted-peers` set, and only accepts ops from peers in that set. The full ACL machinery above is only needed if you want fine-grained per-document access control.

## 7. Impact on the session and groupware models

The session model changes from "connection to a central server" to "local state with peer sync in the background":

```clojure
;; Before (server-centric):
;; (new-session account-id conn) -> atom attached to server state

;; After (local-first):
;; Sessions are local; "connection" to a peer is opportunistic sync,
;; not a prerequisite for working.
(defn start-local-session [peer doc-id]
  (atom {:peer peer
         :doc-id doc-id
         :cursor nil
         :local-ops (atom [])      ;; uncommitted ops made while possibly offline
         :sync-status (atom {})})) ;; which peers are currently reachable
```

The groupware broadcast from the previous answer was a server push; in local-first it becomes gossip — the "driver" in a group session sends view-state ops to known peers, which forward them to peers they know, rather than routing everything through a hub:

```clojure
(defn broadcast-view-state! [local-peer group-id view-state]
  ;; Send to directly connected group members; they gossip onward.
  ;; View-state ops are ephemeral (not journaled) but still signed
  ;; and routed through the same sync transport.
  (doseq [member-peer (group-members group-id)]
    (when (reachable? local-peer member-peer)
      (send-to-peer member-peer {:type :group/view-sync
                                  :view-state view-state
                                  :from (:peer-id local-peer)
                                  :clock (current-clock local-peer)}))))
```

## 8. Testing in a distributed model

Testing local-first systems requires simulating network conditions that don't exist in the original test suite — partitions, reordering, and delayed delivery — because the bugs you're guarding against (divergence, lost ops, inconsistent merge) only manifest under those conditions:

```clojure
(ns nls.test.network)

;; A simulated network that can introduce partitions, delays, and reordering
(defrecord SimNetwork [peers        ;; map of peer-id -> local state atom
                        in-flight    ;; atom: priority queue of {msg, deliver-at-tick}
                        tick         ;; atom: current logical time
                        partition?]) ;; predicate: should this message be dropped?

(defn partition! [net peer-ids]
  (reset! (:partition? net)
          (fn [from to] (and (peer-ids from) (not (peer-ids to))))))

(defn deliver-tick! [net]
  ;; Advance time, deliver all messages due at this tick
  (swap! (:tick net) inc)
  (let [due (filter #(= (:deliver-at %) @(:tick net)) @(:in-flight net))]
    (doseq [{:keys [to msg]} due]
      (receive! (get-peer net to) msg))))

(deftest convergence-after-partition
  (let [net (sim-network [:alice :bob :carol])
        doc-id "shared-doc"]
    ;; Partition Alice from Bob and Carol
    (partition! net #{:alice})
    ;; Both sides make independent edits
    (local-edit! net :alice doc-id {:kind :set-text :node-id :n1 :text "Alice's version"})
    (local-edit! net :bob   doc-id {:kind :set-text :node-id :n2 :text "Bob's addition"})
    ;; Heal partition
    (heal! net)
    ;; Run sync until quiescent
    (run-until-quiescent! net 100)
    ;; All peers must have converged to the same tree
    (is (= (current-tree net :alice doc-id)
           (current-tree net :bob doc-id)
           (current-tree net :carol doc-id))
        "all peers must converge after partition heals")
    ;; Both edits must have survived (no silent data loss)
    (is (= "Alice's version" (text-of (current-tree net :alice doc-id) :n1)))
    (is (= "Bob's addition"  (text-of (current-tree net :alice doc-id) :n2)))))

(deftest journal-is-consistent-across-peers
  (let [net (sim-network [:alice :bob])]
    (save! net :alice "doc1")
    (run-sync! net)
    (save! net :bob "doc1")
    (run-sync! net)
    (is (= (journal/versions net :alice "doc1")
           (journal/versions net :bob  "doc1"))
        "Journal DAG must be identical on all peers after sync")))
```

The property-based test worth investing in most heavily is a **convergence property**: for any two sequences of valid operations applied independently on two peers, syncing always produces the same resulting tree regardless of the order in which ops were applied. This is the fundamental guarantee that local-first is purchasing, and it's the one that's hardest to reason about informally — `test.check` generating random op sequences against random small trees gives you much stronger confidence in it than hand-written examples ever could.

---

## Summary of architectural additions, layered onto what already exists

The existing architecture's *concepts* mostly survive — Journal, session state, groupware groups, graphics — but their *implementation assumptions* about centralization flip in several places:

The Journal moves from sequential file versions on a server to a replicated content-addressed op DAG, modeled on Git's structure, where "versions" are DAG nodes that can have multiple parents when peers merge. Session state moves from server-held atoms to local atoms that sync opportunistically, so work never blocks on network availability. The broadcast/groupware hub model becomes peer gossip, with the "driver" originating view-state messages that route through the peer graph rather than fanning out from a central point. Identity moves from server-authenticated accounts to self-sovereign keypairs, with ops signed at origin so any peer can verify authorship independently. The CRDT conflict-resolution policy from the co-editing design gets promoted from an optional concern to a fundamental architectural layer, since there is no longer a server to serialize concurrent writes before they hit the document state. And the test suite gains a network simulation layer — partitions, delays, reordering — as a first-class test fixture, since the bugs unique to local-first only surface under those conditions.

Prompt: Can forking be used as a CRDT conflict-resolution policy?

Yes — and it's a more philosophically honest policy than silent merging for a document system, because it never destroys information without explicit human intent. But it requires a precise understanding of what "forking" means at each layer of the data model, because the word covers several different things that need to be implemented differently.

## 1. What forking actually means as a CRDT policy

Traditional CRDTs guarantee **convergence** — all peers eventually reach the same state, with conflicts resolved deterministically by the data structure itself (last-writer-wins, union, etc.). Forking as a policy is a deliberate departure from that: when concurrent operations conflict irreconcilably, instead of picking a winner, you **preserve both versions simultaneously** and surface the conflict to the user for explicit resolution.

This is actually a well-defined CRDT type — the **Multi-Value Register (MVR)**. Rather than holding one value, an MVR holds a *set* of concurrent values whenever concurrent writes are detected. Amazon's Dynamo used exactly this approach (calling the concurrent versions "siblings"), and Git's model of merge conflicts is structurally identical. The key property: **no data is ever silently discarded**.

```clojure
(ns nls.mvr)

;; A Multi-Value Register: holds one value under normal conditions,
;; a set of concurrent values when a conflict exists.
(defrecord MVR [values    ;; set of {:value v :clock c :peer-id p}
                resolved?])

(defn write [mvr new-value clock peer-id]
  (let [dominated (filter #(happens-before? (:clock %) clock) (:values mvr))
        surviving (remove (set dominated) (:values mvr))]
    (->MVR (conj surviving {:value new-value :clock clock :peer-id peer-id})
           (= 1 (count surviving)))))

(defn conflicted? [mvr]
  (> (count (:values mvr)) 1))

(defn current-values [mvr]
  (:values mvr))
```

When `conflicted?` returns true, the register holds multiple simultaneous values — the fork. Resolution is explicit:

```clojure
(defn resolve-fork! [mvr chosen-value merged-clock peer-id]
  ;; The resolution is itself a new write that dominates all prior concurrent values.
  ;; This creates a merge node in the DAG — the "parents" are all forked values.
  (->MVR #{{:value chosen-value :clock merged-clock :peer-id peer-id}}
         true))
```

## 2. Forking at different granularities in the NLS model

The system has three data types — outline trees, route graphics, and journal versions — and each needs forking applied at a different granularity.

### Leaf values: text fields on outline nodes

This is the MVR case directly. Two peers concurrently editing a node's text produce two sibling values that coexist until resolved:

```clojure
(defrecord OutlineNode [node-id
                         text      ;; MVR, not a plain string
                         attrs     ;; MVR per attribute
                         children  ;; ordered sequence, separate conflict handling
                         parent-id])

(defn node-text [node]
  (if (conflicted? (:text node))
    {:status :forked
     :versions (current-values (:text node))}
    {:status :resolved
     :value (:value (first (current-values (:text node))))}))
```

The materialized view of a conflicted node shows both values — the client renders them distinctly (e.g. striped or side-by-side) so the user sees the fork rather than having one version silently suppressed.

### Structural operations: moves, deletes, indents

Structural conflicts are more serious than text conflicts because they affect the tree's topology, not just leaf content. Two independent structural operations on the same subtree can produce results that are both locally valid but globally incoherent — for example, one peer moving a node and another peer deleting it, which produces either a ghost (deleted node in a new position) or a phantom (non-deleted node with no parent).

The right fork granularity here is **subtree-level**: when a structural conflict is detected, fork the entire affected subtree rather than trying to merge the individual ops:

```clojure
(defrecord SubtreeFork [fork-id
                         base-node-id    ;; the root of the conflicting subtree
                         versions        ;; map of peer-id -> subtree snapshot
                         ancestor-op-id  ;; last op both peers shared before diverging
                         clocks])        ;; vector clock per version

(defn detect-structural-conflict [op1 op2]
  ;; ops on the same node that are concurrent and structurally incompatible
  (and (concurrent? (:clock op1) (:clock op2))
       (= (:node-id op1) (:node-id op2))
       (structural-op? (:kind op1))
       (structural-op? (:kind op2))))

(defn fork-subtree! [doc node-id op1 op2]
  (let [base-subtree (subtree-at doc node-id)
        v1 (apply-op base-subtree op1)
        v2 (apply-op base-subtree op2)]
    (->SubtreeFork (new-fork-id)
                    node-id
                    {(:peer-id op1) v1 (:peer-id op2) v2}
                    (:op-id (common-ancestor op1 op2))
                    {(:peer-id op1) (:clock op1)
                     (:peer-id op2) (:clock op2)})))
```

The document holds the fork explicitly — it doesn't try to apply either version as "the tree." The rendering layer shows the fork to the user as a visible divergence rather than a resolved tree.

### Journal versions: already a DAG, forks are native

This is the most natural layer — the Journal DAG from the previous design already *is* a fork structure. Two peers saving independently create two tips with no shared descendant:

```
        v1 (base)
       /          \
   v2 (alice)    v3 (bob)    ← concurrent saves: two DAG tips = a fork
       \          /
         v4 (merge)          ← explicit resolution: merge commit, two parents
```

The fork-as-CRDT-policy means: **don't hide this DAG shape from the user**. Surface it as "this document has two current versions" and provide tools to resolve. This is where the design diverges most sharply from the previous "last-writer-wins" approach — the Journal becomes the primary UI for conflict visibility, not just an audit trail.

## 3. The fork resolution workflow as NLS commands

A fork without resolution tooling is just data accumulation — you need explicit commands for users to navigate, compare, and resolve forks. These map naturally into the chord/command system:

```clojure
;; Command registry additions for fork management
(defcommand list-forks 28 [session]
  ;; Show all current unresolved forks in the active document
  (let [forks (find-forks (active-doc session))]
    (emit! session :forks/list {:forks forks})))

(defcommand navigate-to-fork 29 [session]
  ;; Move cursor to the next unresolved fork node (like a spell-checker)
  (swap! session update :cursor jump-to-next-fork (active-doc session)))

(defcommand inspect-fork 30 [session]
  ;; Show both/all versions of the current fork side-by-side
  (let [fork (fork-at-cursor session)]
    (emit! session :forks/inspect {:fork fork
                                    :versions (:versions fork)})))

(defcommand resolve-fork 31 [session]
  ;; Apply the designated version as the resolution — uses the
  ;; "bug" designation mechansim: user designates their preferred version,
  ;; then chords this command to resolve.
  (let [chosen-version (designated-fork-version session)]
    (resolve-fork! (active-doc session)
                   (fork-at-cursor session)
                   chosen-version
                   (current-clock (:peer session)))))
```

The designation mechanism from the earlier design turns out to be exactly the right input model for fork resolution: the user visually designates which version they want (pointing at one of the two displayed variants), then chords "resolve" — the same tri-modal input model used for everything else, applied to conflict resolution.

## 4. How forking changes the sync protocol

The anti-entropy gossip from the previous design needs one addition: when receiving ops that would create a conflict with local state, the receiver must **record the fork** rather than silently applying a resolution:

```clojure
(defn receive-and-apply-ops! [local-peer incoming-ops]
  (doseq [op incoming-ops]
    (if-let [conflict (detect-conflict local-peer op)]
      ;; Fork: record both versions, don't resolve automatically
      (do (record-fork! local-peer conflict op)
          (emit-notification! local-peer :fork/created conflict))
      ;; No conflict: apply normally
      (apply-op! local-peer op))))
```

This means the sync protocol's job is not to produce convergence (same state everywhere) but to produce **consistent fork visibility** (same forks visible everywhere, even if unresolved). All peers know about all forks; they may have different local resolutions pending. This is a subtler invariant than simple convergence, and it needs to be tested explicitly:

```clojure
(deftest sync-propagates-forks-not-resolutions
  (let [net (sim-network [:alice :bob :carol])]
    ;; Alice and Bob independently edit the same node while partitioned
    (partition! net #{:alice})
    (local-edit! net :alice "doc1" {:kind :set-text :node-id :n1 :text "Alice"})
    (local-edit! net :bob   "doc1" {:kind :set-text :node-id :n1 :text "Bob"})
    (heal! net)
    (run-until-quiescent! net 100)
    ;; All three peers must see the fork — not one peer's resolution
    (is (conflicted? (node-text (node-at (current-doc net :alice "doc1") :n1))))
    (is (conflicted? (node-text (node-at (current-doc net :bob   "doc1") :n1))))
    (is (conflicted? (node-text (node-at (current-doc net :carol "doc1") :n1))))
    ;; Both values must be present on all peers
    (is (= #{"Alice" "Bob"} (fork-values net "doc1" :n1)))))
```

## 5. Cascading forks and the depth problem

The honest difficulty with forking as a policy: forks can cascade. A user who resolves a text fork creates a new op; if another peer resolves the same fork differently while offline, you now have a fork-of-a-resolution — a second-order conflict. Left unmanaged, this produces an exponentially growing conflict DAG.

Three mitigations worth building in from the start:

**Fork expiry for ephemeral content**: view-state and presence forks (where the driver's cursor was in a groupware session) should have a TTL and auto-resolve to the most recent value once they're old enough — they're not worth surfacing as conflicts to the user.

```clojure
(defn maybe-auto-resolve! [fork]
  (when (and (ephemeral-fork? fork)
             (> (age-ms fork) 5000))
    (resolve-fork! fork (most-recent-version fork) :auto)))
```

**Forking depth limit**: don't allow forks to cascade beyond a configurable depth — if a fork already has an unresolved resolution conflict, require the user to resolve the base fork first before creating new ops on either branch. This prevents unbounded proliferation.

**Fork visibility as a first-class document status**: the Journal's version list should show fork state prominently — "this document has 2 open forks" as a top-level property, not buried in individual node state — so users understand the document's overall health at a glance.

## 6. What forking preserves that silent merging loses

The philosophical case for forking as a policy, and why it fits the NLS lineage particularly well: Engelbart's core thesis was **augmenting human intellect**, not automating human decisions. Silent conflict resolution (any form of automatic merge) makes a semantic decision — "these two intents are equivalent, or one should win" — that in general only a human can make correctly for structured knowledge documents. An outline node saying "stores to visit on the way home" that two people have renamed to different things represents a genuine semantic divergence, not a technical conflict to be automatically resolved.

Forking surfaces that divergence honestly and gives the human the tools to resolve it intentionally — which is more consistent with the augmentation philosophy than any algorithm that silently picks a winner, however cleverly designed.

The cost is UI complexity and the risk of fork accumulation — but those are manageable engineering problems, whereas silent data loss in a knowledge management system is a fundamental trust problem that's much harder to recover from once users encounter it.

Prompt: How can the equivalent of a pull-request be implemented for fork resolution?

A pull request in this context is exactly the right abstraction: it's a structured, asynchronous, human-mediated process for reviewing a proposed fork resolution before it becomes part of the shared document history — with discussion, revision, and explicit acceptance/rejection. In Git-hosted systems this lives outside the version control layer itself (GitHub/GitLab provide it as a service on top of Git). In your local-first NLS system, it needs to live *inside* the protocol — there's no central hosting service to delegate to, so the pull-request machinery needs to be a first-class document type that replicates peer-to-peer alongside the documents it governs.

## 1. The pull request as a document type

Just as `RouteGraphic` was a new sibling artifact type alongside OPML documents, a pull request is a new artifact type that *references* a fork and a proposed resolution:

```clojure
(ns nls.pr)

(defrecord PullRequest [pr-id
                         doc-id           ;; document containing the fork
                         fork-id          ;; the specific fork being resolved
                         author-peer      ;; peer proposing the resolution
                         base-version-ids ;; set of Journal DAG tips being merged
                         proposed-ops     ;; the resolution ops, not yet applied to doc
                         status           ;; :open :accepted :rejected :withdrawn :superseded
                         reviewers        ;; map of peer-id -> {:status :vote :comment}
                         discussion       ;; ordered log of Discussion entries
                         created-at       ;; Lamport timestamp
                         resolved-at])    ;; nil until closed

(defrecord Discussion [entry-id
                        author-peer
                        body              ;; plain text or outline fragment
                        quoted-op-ids     ;; ops in the PR being discussed
                        clock             ;; vector clock — discussion itself is a CRDT
                        parent-entry-id]) ;; threading
```

The pull request is itself subject to local-first replication — it's stored in the Journal alongside the documents it governs, replicated to all peers who have access to the document, and its own `discussion` field is a CRDT (an append-only log of signed entries, naturally a grow-only set). This means PR discussion works offline too: a reviewer can write comments while disconnected, and they sync when they reconnect.

## 2. The PR lifecycle as a state machine

Making the lifecycle explicit as a state machine (rather than ad hoc status strings) gives you a precise spec to test against and a clear extension point for new states:

```clojure
(ns nls.pr.fsm)

(def transitions
  {:open      #{:accepted :rejected :withdrawn :superseded}
   :accepted  #{}       ;; terminal — resolution committed to Journal
   :rejected  #{:open}  ;; can be reopened with revised ops
   :withdrawn #{:open}  ;; author withdrew, but may reopen
   :superseded #{}})    ;; another PR resolved the same fork first (terminal)

(defn transition! [pr new-status peer-id clock]
  (assert (contains? (transitions (:status pr)) new-status)
          (str "Invalid transition: " (:status pr) " -> " new-status))
  (-> pr
      (assoc :status new-status)
      (update :discussion conj
              (->Discussion (new-id) peer-id
                             (str "Status changed to " new-status)
                             [] clock nil))))

(defn can-accept? [pr peer-id policy]
  ;; Policy is pluggable — see section 4
  ((:accept-predicate policy) pr peer-id))
```

The `superseded` terminal state handles the local-first-specific case: two peers independently open PRs for the same fork, one gets accepted while the other is still open — the second automatically becomes superseded rather than being left as a phantom open PR. This needs detection in the sync layer:

```clojure
(defn detect-superseded! [local-peer doc-id fork-id]
  ;; Called during sync when a resolution for fork-id arrives from another peer
  (doseq [open-pr (open-prs-for-fork local-peer doc-id fork-id)]
    (when (not= (:pr-id open-pr) (:resolving-pr-id (fork-resolution doc-id fork-id)))
      (transition! open-pr :superseded (:peer-id local-peer) (current-clock local-peer)))))
```

## 3. Creating a PR: proposing a resolution

Creating a PR doesn't apply ops to the document — it stages them for review. The proposed ops live in the PR record, not in the document, until acceptance:

```clojure
(defn open-pr! [local-peer doc-id fork-id resolution-ops message]
  (let [fork (get-fork (active-doc local-peer doc-id) fork-id)
        pr   (->PullRequest
               (new-pr-id)
               doc-id
               fork-id
               (:peer-id local-peer)
               (set (keys (:versions fork)))   ;; the DAG tips being merged
               resolution-ops
               :open
               {}
               [(->Discussion (new-id) (:peer-id local-peer) message [] (current-clock local-peer) nil)]
               (tick-clock local-peer)
               nil)]
    (store-pr! local-peer pr)
    (broadcast-to-peers! local-peer :pr/opened pr)
    pr))
```

The `resolution-ops` are the specific ops that would resolve the fork — text choices, structural decisions — expressed in the same op format used for ordinary edits. This is important: a reviewer can read exactly what would change, and the apply step (on acceptance) is just feeding these ops through the existing `apply-op!` machinery.

## 4. Review policies: pluggable acceptance criteria

NLS served a small expert team where informal consensus was sufficient; a larger deployment might need formal voting. Make the acceptance policy a first-class pluggable:

```clojure
(ns nls.pr.policy)

(defprotocol ReviewPolicy
  (accept-predicate [policy pr peer-id]
    "Returns true if this peer's vote/action should accept the PR")
  (auto-accept? [policy pr]
    "Returns true if the PR should auto-accept without further review")
  (quorum-met? [policy pr]
    "Returns true if enough reviewers have approved"))

;; For a small trusted team (Engelbart's original NLS use case):
;; author can self-merge, or any single other peer can approve.
(defrecord SingleApprovalPolicy []
  ReviewPolicy
  (accept-predicate [_ pr peer-id]
    (or (= peer-id (:author-peer pr))
        (= :approved (get-in pr [:reviewers peer-id :status]))))
  (auto-accept? [_ pr] false)
  (quorum-met? [_ pr]
    (or (some #(= :approved (:status %)) (vals (:reviewers pr)))
        true)))  ;; author can always self-merge

;; For a larger team requiring consensus:
(defrecord QuorumPolicy [required-approvals]
  ReviewPolicy
  (accept-predicate [_ pr peer-id]
    (= :approved (get-in pr [:reviewers peer-id :status])))
  (auto-accept? [_ pr] false)
  (quorum-met? [this pr]
    (->> (vals (:reviewers pr))
         (filter #(= :approved (:status %)))
         count
         (<= (:required-approvals this)))))

;; For automated content (e.g. a bot resolving trivial whitespace forks):
(defrecord AutoMergePolicy [trust-predicate]
  ReviewPolicy
  (accept-predicate [_ _ _] false)
  (auto-accept? [this pr]
    ((:trust-predicate this) pr))
  (quorum-met? [_ _] true))
```

The policy is stored per-document in the document's ACL record (from the identity design in the previous answer), so different documents in the same peer network can have different review requirements.

## 5. The review workflow: discussion as a CRDT

Discussion entries are themselves a CRDT — a grow-only set of signed, causally ordered entries. This means reviewers can comment while offline and their comments sync without conflict:

```clojure
(defn add-comment! [local-peer pr body quoted-op-ids parent-entry-id]
  (let [entry (->Discussion (new-id)
                              (:peer-id local-peer)
                              body
                              quoted-op-ids
                              (tick-clock local-peer)
                              parent-entry-id)]
    (update-pr! local-peer (:pr-id pr)
                update :discussion conj entry)
    (broadcast-to-peers! local-peer :pr/comment {:pr-id (:pr-id pr) :entry entry})))

(defn approve! [local-peer pr]
  (update-pr! local-peer (:pr-id pr)
              assoc-in [:reviewers (:peer-id local-peer)]
              {:status :approved :clock (tick-clock local-peer)}))

(defn request-changes! [local-peer pr comment]
  (add-comment! local-peer pr comment [] nil)
  (update-pr! local-peer (:pr-id pr)
              assoc-in [:reviewers (:peer-id local-peer)]
              {:status :changes-requested :clock (tick-clock local-peer)}))
```

The threaded discussion structure (`parent-entry-id`) lets reviewers quote specific proposed ops — "I disagree with this text choice on node N, because..." — creating a fine-grained conversation tied to specific resolution decisions, not just the PR as a whole.

## 6. Applying an accepted PR: committing the resolution

When a PR is accepted, its proposed ops are applied to the document and a merge commit is written to the Journal:

```clojure
(defn accept-and-commit! [local-peer pr policy]
  (assert (quorum-met? policy pr) "Quorum not met")
  (let [doc (active-doc local-peer (:doc-id pr))
        ;; Apply the staged resolution ops — same path as any normal op
        resolved-doc (reduce apply-op! doc (:proposed-ops pr))
        ;; Write a merge commit to the Journal with multiple parents —
        ;; the DAG fork is sealed here with a resolution node
        merge-version (journal/save-merge!
                        local-peer
                        (:doc-id pr)
                        resolved-doc
                        {:parent-ids (:base-version-ids pr)
                         :pr-id (:pr-id pr)
                         :resolution-authors (keys (:reviewers pr))})]
    ;; Close the PR
    (transition! pr :accepted (:peer-id local-peer) (current-clock local-peer))
    ;; Invalidate other open PRs for the same fork
    (detect-superseded! local-peer (:doc-id pr) (:fork-id pr))
    ;; Broadcast the merge to all peers
    (broadcast-to-peers! local-peer :pr/accepted
                           {:pr pr :merge-version merge-version})))
```

The `journal/save-merge!` creates a DAG node with multiple parents — one per forked version being merged — which is the local-first equivalent of a Git merge commit. This node permanently records not just *what* the resolution was, but *which PR* produced it and *which peers* approved it, making the Journal a complete audit trail of all conflict resolutions, not just document states.

## 7. NLS commands for the PR workflow

These map to the chord/command system, continuing the pattern from before:

```clojure
;; PR creation — from the fork inspection view
(defcommand open-pull-request 24 [session]
  (let [fork (fork-at-cursor session)
        staged-ops (staged-resolution-ops session)]
    (open-pr! (:peer @session) (:doc-id @session) (:fork-id fork) staged-ops "")))

;; PR navigation
(defcommand next-open-pr 25 [session]
  (swap! session update :cursor jump-to-next-pr
         (open-prs (:peer @session) (:doc-id @session))))

;; Reviewing
(defcommand approve-pr 26 [session]
  (approve! (:peer @session) (current-pr session)))

(defcommand request-changes-pr 27 [session]
  ;; Uses the currently drafted text in the session's edit buffer as the comment body
  (request-changes! (:peer @session) (current-pr session) (current-edit-buffer session)))
```

## 8. Testing the PR system

The PR system needs tests at three levels: state machine correctness, concurrent PR races, and full lifecycle integration.

**State machine tests** — exhaustive transition coverage:

```clojure
(deftest invalid-transitions-are-rejected
  (let [pr (open-test-pr)]
    (is (thrown? AssertionError
                 (transition! (assoc pr :status :accepted) :open :alice clock))
        "accepted PRs cannot be reopened")))

(deftest accepted-pr-cannot-transition
  (let [pr (assoc (open-test-pr) :status :accepted)]
    (doseq [status [:rejected :withdrawn :superseded :open]]
      (is (thrown? AssertionError (transition! pr status :alice clock))))))
```

**Concurrent PR race — the hardest case:**

```clojure
(deftest concurrent-prs-for-same-fork-one-supersedes
  (let [net (sim-network [:alice :bob :carol])
        doc-id "shared-doc"
        fork-id (create-test-fork! net doc-id)]
    ;; Alice and Bob both open PRs while partitioned from each other
    (partition! net #{:alice})
    (open-pr! net :alice doc-id fork-id alice-ops "Alice's resolution")
    (open-pr! net :bob doc-id fork-id bob-ops "Bob's resolution")
    ;; Bob's gets accepted first (while Alice is still partitioned)
    (approve! net :carol (:id (bob-pr net doc-id)))
    (accept-and-commit! net :carol (bob-pr net doc-id) single-approval-policy)
    ;; Heal partition — Alice's PR should become superseded on sync
    (heal! net)
    (run-until-quiescent! net 100)
    (is (= :superseded (:status (alice-pr net doc-id)))
        "Alice's PR must be superseded after Bob's was accepted and synced")
    (is (= :accepted (:status (bob-pr net doc-id))))
    (is (= 1 (count (open-prs net doc-id)))
        "no orphaned open PRs should remain after a fork is resolved")))
```

**Discussion CRDT — offline comment sync:**

```clojure
(deftest offline-comments-sync-without-conflict
  (let [net (sim-network [:alice :bob])
        pr (open-test-pr net "doc1")]
    ;; Both comment while partitioned
    (partition! net #{:alice})
    (add-comment! net :alice pr "I prefer version A" [] nil)
    (add-comment! net :bob pr "I prefer version B" [] nil)
    (heal! net)
    (run-until-quiescent! net 100)
    ;; Both comments must appear on both peers — no comment lost
    (is (= 2 (count (discussion-entries net :alice pr))))
    (is (= 2 (count (discussion-entries net :bob pr))))
    (is (= (set (discussion-entries net :alice pr))
           (set (discussion-entries net :bob pr))))))
```

**Full lifecycle integration:**

```clojure
(deftest full-pr-lifecycle
  (let [net (sim-network [:alice :bob :carol])
        doc-id "shared-doc"
        fork-id (create-test-fork! net doc-id)
        pr (open-pr! net :alice doc-id fork-id alice-ops "Resolve: prefer Alice's naming")]
    ;; Review cycle
    (add-comment! net :bob pr "Can you explain why you chose this name?" [] nil)
    (is (= 1 (count (discussion-entries net :bob pr))))
    (add-comment! net :alice pr "It matches the OPML heading convention" [] (:entry-id (first-comment pr))))
    ;; Carol requests a small change; Alice revises and resubmits
    (request-changes! net :carol pr "Please also update the linked graphic label")
    (revise-pr! net :alice pr (conj alice-ops graphic-label-op))
    ;; Approval and commit
    (approve! net :carol pr)
    (accept-and-commit! net :alice pr single-approval-policy)
    ;; Verify Journal state
    (let [versions (journal/versions net :alice doc-id)]
      (is (some #(= :merge (:kind %)) versions)
          "Journal must contain a merge commit")
      (is (= (:pr-id pr) (:pr-id (merge-commit versions)))
          "merge commit must reference the PR that produced it"))
    ;; Verify fork is cleared
    (is (empty? (open-forks net :alice doc-id)))))
```

---

The key insight that makes pull requests fit naturally here: they are not a layer on top of the version control system (as GitHub is on top of Git) but a **first-class document type within it**, subject to the same local-first replication, the same CRDT discussion semantics, and the same Journal audit trail as the documents they govern. The PR's proposed ops, its discussion, its reviewer votes, and its final merge commit are all data that replicate peer-to-peer, so the review process works fully offline and the complete decision history is permanently preserved alongside the document history — which is exactly the kind of augmented record-keeping that NLS was designed to support in the first place.

Prompt: Write a story about a distributed team using this system in an augmented reality environment where they can meet virtually at times convenient for them, co-work with other team members who are present, leave notes on shared boards in the environment, and optimize team productivity towards a project goal.

# The Oaks Project

## Part One: Morning, Different Mornings

Yuki's alarm hadn't gone off yet when the soft chime of an incoming annotation pulled her into partial wakefulness. She lay still for a moment, the ceiling of her Kyoto apartment pale in the pre-dawn grey, then touched the small node behind her left ear. The overlay bloomed across her vision — not the full environment, just a notification ribbon in the peripheral field she'd configured for sleep-adjacent hours. Someone had left a note on the Oaks board.

She recognized the glyph signature before she read the content: Amara, from Accra, which meant it was early evening there. The note was attached to a branch of the shared outline that Yuki had last touched two days ago — a structural problem in the project's third phase that neither of them had managed to untangle.

*I think I see it,* the note said. *The dependency isn't where we thought. Look at the route map — the line from node seven to node twelve crosses itself when you expand to depth three. I've opened a fork on the planning subtree. Don't resolve it yet. I want Dmitri to see both versions first.*

Yuki smiled at the ceiling. She pulled up the route map in her peripheral vision and immediately saw what Amara meant. The line crossed itself. Of course it did.

She left her own note, a small voice-annotated chime attached to Amara's: *Saw it. Agree. Will be in the room at fourteen hundred Kyoto. Leave the fork open.*

Then she let the overlay recede and slept another hour.

---

In Nairobi, Marcus was eating breakfast on a small balcony overlooking a courtyard full of jacaranda trees. He wore light AR glasses rather than the contact overlay — he'd never fully trusted the neural interface, which was a reasonable position given that he'd helped write two of the security audits for the previous generation of the hardware. He understood exactly which threat vectors remained unresolved.

Through the glasses, the shared workspace floated above his coffee cup, anchored to the courtyard wall by his personal spatial configuration. The Oaks environment had a specific aesthetic the team had negotiated over the first two weeks of the project: a tall-ceilinged reading room, dark wood and high windows, bookshelves lining the walls that were actually the archived Journal versions of the project documents, rendered as physical volumes whose thickness corresponded to the number of versions they contained. The planning document was nearly four centimeters thick by now. The graphics document — Amara's route maps — was slimmer but taller, an oversized atlas.

Marcus navigated to the shared board nearest the door, the one they used for daily status. His own zone of the board — each team member had a physical area marked by a subtle floor pattern — showed three items he'd left yesterday. He updated the first one: the authentication layer in the peer sync protocol had passed its test suite overnight. He marked it complete, and the item's color shifted from amber to a deep green that he'd chosen himself because he found traffic-light red-green systems imprecise about the intermediate states. His green meant *done and verified.* Amber meant *in progress and on track.* A particular shade of blue he thought of as slate meant *blocked, needs a human.* There was one slate item on his board, and it had been there for six days.

He looked at it the way you look at a sore tooth. The sync protocol's fork resolution timing had an edge case he couldn't reproduce consistently — a race condition that appeared only when three or more peers simultaneously opened pull requests for the same fork while one of them was experiencing intermittent connectivity. He'd documented it exhaustively. The documentation was a small, precise book on the shelf behind him, three versions deep. He still didn't know what caused it.

He left a new note on the board, addressed — by peer-glyph — to the whole team: *Slate item six still open. If anyone has spare cycles today to pair on the timing issue, I'll be in the room from eleven to thirteen Nairobi time. The test harness is set up. I just need another pair of eyes.*

He finished his coffee. The jacaranda petals fell in the windless morning.

---

Dmitri was on a train.

This was not unusual. Dmitri spent a significant portion of his working life on trains, which he defended to anyone who asked by pointing out that trains produced the precise quality of motion and white noise that allowed him to think at a particular depth that his apartment in St. Petersburg never quite managed. He had a reserved compartment, a small fold-down table, and a window that showed birch trees in the long Russian morning light.

He was reading the Journal.

Not the project Journal specifically — though he had that open in a secondary pane — but a private habit he'd developed over the years of keeping a personal annotation layer on top of whatever shared document he was currently working in. His annotations were visible only to him. They were, he'd decided long ago, how he actually thought: a running commentary on the document that was sometimes disagreement, sometimes elaboration, sometimes a single word that he'd return to days later and find had unlocked something he hadn't been ready to understand when he wrote it.

The Oaks project Journal showed a fork. He'd seen Amara's note. He'd seen Yuki's response. He read both branches of the fork slowly, the train carrying him through the birch trees, and he wrote a single private annotation that said: *The question is whether the dependency is sequential or conditional. Amara thinks sequential. The route map says conditional. These are not the same resolution.*

He opened a pull request.

It was different from either Amara's forked version — it proposed a third reading of the planning subtree that treated the dependency as conditional on a variable that neither of the existing versions had named explicitly. He wrote a long comment in the PR discussion, explaining the distinction carefully, with a route map annotation that added a new labeled point to Amara's graphic and drew a dotted line — indicating conditionality rather than the solid lines used for sequential dependency — between node seven and a new node he'd added, labeled *availability threshold.*

He addressed it to Amara and Yuki, with a courtesy notification to Marcus, and set his reviewer policy to *single approval, author can merge.* Then he put the fold-down table up, watched the birch trees for a while, and let his thinking run ahead of his documentation, which was usually where his best work happened.

---

## Part Two: The Room

At fourteen hundred Kyoto time — which was eight hundred in Accra, nine hundred in Nairobi, ten hundred in St. Petersburg, and one moment on Dmitri's train when the birch trees gave way to a long flat field — four people entered the same room that did not exist in any single place.

It was the reading room. The dark wood, the high windows, the shelves of Journal volumes. A long oak table in the center, which was the design choice the project had been named for, though this had only become clear to new team members gradually and was never stated directly. The floor pattern shifted subtly to show each person's presence zone, not to separate them but to give spatial reference — in a shared virtual environment, knowing where someone is *from* matters more than where they are.

Yuki arrived first and was already standing at the route map when Amara's presence chimed in. Amara materialized — that was the word they all used without self-consciousness — at her usual position near the south-facing window, where the rendered light was warmest at this hour, a choice she'd made in the first week and kept without mentioning it.

"You saw the dotted line," Yuki said, without preamble.

"I saw it." Amara walked to the map. The route graphic was projected on the wall beside the bookshelf, larger than its document form, and Dmitri's new labeled point — *availability threshold* — floated above the map surface in a slightly different rendering style, indicating it was part of an unmerged PR. "He's right that it changes things. I'm not sure he's right about *what* it changes things to."

Marcus arrived and assessed the room quickly, the way he always did. Board first, then the map, then the people. "Dmitri's not here yet."

"He's on the train. He might drop in as audio-only." Yuki gestured at the PR discussion, which was visible as a floating panel beside the map. "Read his comment."

Marcus read it. He was quiet for longer than the comment probably required.

"He's describing a state machine," he said finally.

"He's describing a dependency that only activates under a condition we haven't formally defined," Amara said.

"Which is a state machine."

Amara considered this. "Yes."

"Then I know what's causing the slate item." Marcus turned to the board and looked at his six-day-old blue tile with an expression that mixed relief with the particular frustration of having been very close to something for a long time without quite seeing it. "The fork resolution timing issue. The race condition. It only happens with three peers and intermittent connectivity because those are exactly the conditions under which a conditional dependency in the sync protocol becomes ambiguous. The peers can't agree on whether the condition is met because they each have different local views of the availability threshold."

The room was quiet for a moment. Somewhere in the environmental ambient layer — a design choice the team had made together, rejecting both silence and music in favor of something textured but unobtrusive — there was the faint sound of a building that had weather outside its walls.

Dmitri arrived as audio, his voice placed spatially near his usual chair at the table, present without being fully rendered. "I heard the last part," he said. "I was waiting to see if someone would get there."

"You knew," Marcus said.

"I thought. It's different."

"Your dotted line is a state transition," Amara said. "Not a route."

"Everything on a route map is a state transition," Dmitri said, with the precision of someone who had been thinking about this on a train for several hours. "The solid lines just hide it."

---

## Part Three: Work

They worked.

This was the part that outsiders — people who encountered shared virtual workspaces in demonstrations or press coverage — consistently underestimated. The environments looked like meeting rooms, which led to the assumption that what happened inside them was meetings. But the Oaks reading room was almost never used for discussion in the formal sense. It was used for *proximate work* — each person doing their own task in the presence of others doing their own tasks, with a low barrier to brief, high-bandwidth exchange when the work itself demanded it.

Amara sat at her end of the table and opened the route map editor. She was revising the graphic in light of Dmitri's dotted line, not because she'd formally accepted his PR yet — she hadn't — but because her own thinking had moved and the graphic needed to move with it. She added three new points, two solid lines, and a dotted line of her own, connecting the *availability threshold* node to a point she labeled *consensus window.* She was working quickly, the way people work when they're translating thought into form faster than they're evaluating it.

Marcus was at the board, not the shared board but his private debugging workspace, which he'd configured as a separate surface on the east wall. The test harness for the race condition was running. He was watching the event log with the focused attention of someone who now knew what they were looking for, which was entirely different from the generalized attention of someone who didn't. He'd marked the slate tile amber. He expected to mark it green before he left the room.

Yuki was in the Journal.

She had pulled three archive volumes from the shelf — rendered as physical books, which she found useful because thickness and weight gave her intuitive information about a document's history that version numbers didn't — and she was reading the project's planning document in deep time, meaning she was tracking how specific decisions had evolved across versions. There was a pattern here. She'd sensed it for a week. She was now close enough to name it: every time the team had revised their model of the project's dependency structure, they had done so in response to a conflict that had first appeared as a fork. The forks weren't problems. The forks were instruments of precision. The document couldn't say what it didn't yet know, and the fork was the shape of not-yet-knowing, held open long enough to be examined.

She started writing a note. It was long for a board note, more like a short document, and she addressed it to the whole team. She wrote about the pattern she'd observed. She wrote carefully, because she knew Dmitri would read it on a train and she wanted the shape of the idea to survive the compression of his particular reading style. She attached links to four specific fork-resolution events in the Journal, each one a version node with two parents, each one a moment where the team's understanding had genuinely advanced.

She was still writing when Amara said: "I've revised the map. I want to show everyone before I amend the PR."

They gathered at the wall. The route graphic was different now — more complex in one region, simpler in another, with the two dotted lines creating a visual grammar that distinguished sequential from conditional dependency across the whole map. It was clearer than it had been. It was also, Yuki noticed, clearly not finished.

"The consensus window needs a label that describes what crosses it," Dmitri said from his chair-position. "Right now it's a point on the map without a legend entry."

"I know," Amara said. "I don't know what to call it yet."

"Call it what it is," Marcus said. He was still watching the event log with half his attention, but his voice had the quality of someone speaking from a conclusion they'd just reached. "It's the moment when the peers agree on the state. Call it *quorum point.*"

Amara looked at the map. She added the legend entry. The dotted line from *availability threshold* to *quorum point* sat in the graphic and became, immediately, the clearest thing in it. The kind of clarity that makes everything around it look as though it had been waiting for exactly this.

"I'll amend the PR," she said.

---

## Part Four: Notes Left in the Room

Marcus marked the slate tile green at twelve forty Nairobi time. He documented the fix in a new Journal version, wrote a thorough comment in the PR discussion connecting the sync protocol issue to the dependency model the map had clarified, and addressed it to the full team. Then he sat for a moment in his presence zone, the debugging workspace behind him quiet, and looked at the reading room.

He'd worked in many kinds of distributed environments. Video grids. Chat threads. Shared documents without spatial anchoring, which he thought of as working in a pile rather than in a room. This was different. He wasn't sure he could specify precisely what made it different, which meant he probably needed to leave a note about it.

He left the note on the shared board in the general zone — the area in the center, between the four presence zones, which the team used for things that didn't belong to any one person. The note said: *Fixed the race condition. The fix came from a route map. I want to mark that down because it's not obvious that fixing a sync protocol bug should involve route maps, and if I don't write it down it will become obvious in retrospect and we'll lose the actual path.*

Dmitri's voice responded, though his presence hadn't shifted: "Nothing is obvious in retrospect. Retrospect is a story we tell about paths we can no longer see."

"That's going in my personal Journal," Yuki said.

"Please attribute it correctly. I want credit."

---

Amara finished revising the pull request at sixteen hundred Accra time, with the evening light coming warm and horizontal through the rendered high windows of the reading room, which she'd tuned to match the actual light in her actual room, because she saw no reason to be in two places at once when one of them could be made accurate. She'd written a long discussion comment explaining the entire revision — the new points, the legend update, the distinction between the two dotted line styles she'd introduced — and she'd addressed it to Dmitri, who had authored the original PR, with the implicit suggestion that he should accept or amend before she merged.

She then did something she did at the end of every substantial piece of work in the shared environment, which was to walk the room.

This was a personal ritual, invisible to the others unless they happened to observe her presence marker moving without apparent purpose. She walked the perimeter of the reading room. She looked at the shelves — the Journal volumes, the project's entire history rendered as physical mass. She looked at the boards, all four presence zones plus the general center. She looked at the route map on the wall, now showing Dmitri's conditional dependency and her quorum point and the whole clearer structure of how the project's phases actually connected to each other.

She was checking for resonance. This was the word she used privately for what she was doing: walking the room until she felt the accumulated work of the day as a single thing rather than a series of events. The room held it. That was what rooms were for. A physical room accumulated the residue of the work done in it — the coffee rings, the erased whiteboard ghosts, the papers left on chairs — and that residue was information, low-density but real, about how the work had moved.

The digital room held it differently but held it nonetheless. The notes on the boards. The revised map. The new Journal volumes, their spines flush with the others but their rendering slightly warmer, indicating they were today's versions, not yet aged into the archive color. The PR panel still floating beside the map, open, awaiting Dmitri's response on a train somewhere past the birch trees.

She left her own note in the general zone, next to Marcus's. It said: *Good day. The fork was the right shape for this problem. See you tomorrow.*

---

## Epilogue: The Journal Remembers

Six months later, a new team member named Priya joined the Oaks project for its final phase. Her onboarding consisted largely of time spent in the reading room alone, walking the shelves, opening the Journal volumes, reading the route maps in their accumulated versions — the early sparse graphics and the later complex ones, each revision preserved and navigable, each fork visible as a DAG node with two parents and a merge commit that recorded who had resolved it and how and why.

She found the day she thought of as the dotted line day — though she hadn't been there and didn't know it by that name — by noticing that four Journal volumes all had new versions created within the same two-hour window. She read them in parallel, opening four books at once on the long oak table, and she followed the thread from Amara's route map through Dmitri's PR through Marcus's fix to Yuki's note about forks as instruments of precision.

She sat with it for a while.

Then she left a note in the general zone, addressed to the whole team, past and present and future. It said: *I understand now how this project thinks. Thank you for leaving the path.*

The room held it. That was what rooms were for.

Prompt: Continue the story with this twist: One person in the group violates their terms of employment and the group needs to move forward without them.  Explain how the encryption features of decentralized data would be used to rekey their entire environment to form a new web of trust with perfect forward secrecy for the remaining employees.

# The Oaks Project, Continued

## Part Five: The Anomaly

Priya found it on a Tuesday.

She had been in the project for three weeks and had developed the habit of arriving in the reading room early, before anyone else, to walk the shelves and orient herself in the accumulated history of the work. She had good instincts for document archaeology — her previous work had involved reconstructing the decision trails of projects that had gone wrong, finding the moments where understanding had diverged from reality and the team hadn't noticed until much later. She did not expect to need those instincts here. She had been finding the Oaks project unusually legible, its history unusually honest.

She was looking at the route map archive when she noticed the anomaly.

Not in the map itself. In the access log that floated as a subtle overlay beside the archive shelf, visible only if you were looking for it. A faint rendering in the peripheral annotation layer, the kind of information the environment surfaced without foregrounding, because the design philosophy held that ambient awareness should be available without being intrusive.

A Journal volume had been opened. Read from outside the environment. Not through the normal peer sync protocol, which would have shown as a standard replication event with the originating peer's glyph. Through something else — an access pattern that had the shape of an export rather than a sync. The data had left the trust boundary.

The volume was the planning document. The version that contained the dependency model, the quorum point, the full technical architecture of the sync protocol. The version that contained, if you read it carefully and knew what you were looking at, the complete structural logic of the Oaks project's core innovation.

Priya stood very still in the reading room, looking at the access log, not yet willing to follow the implication to its conclusion. Then she followed it.

The export had originated from Kenji's peer node.

She had never met Kenji in person. None of them had met any of the others in person, which was ordinary. She knew him as a presence in the room, a glyph signature, a thoughtful and sometimes slow reviewer of pull requests. He had been on the project since its second month. He sat in his presence zone near the north window and wrote careful comments in PR discussions and occasionally left notes on the general board that had the quality of someone who was listening more than he was speaking.

She looked at the access log for a long time.

Then she opened a private channel — encrypted, point-to-point, using the emergency contact protocol that the project's security documentation described but that she had assumed was theoretical — and she sent a message to Marcus.

*I need you to look at something. Not in the shared room. Privately. Now, if you can.*

---

## Part Six: What Marcus Found

Marcus was at his breakfast balcony when Priya's message arrived. The jacaranda trees were flowering again; it was that time of year. He read the message, and something in the phrasing — *not in the shared room* — made him put down his coffee with more care than the action required.

He opened a sandboxed environment, isolated from the project network, and accepted Priya's secure connection. She shared the access log annotation. He looked at it for less time than she had before reaching the same conclusion.

"When did this happen?" he asked.

"Eleven days ago." She paused. "I've been here three weeks. I didn't know what I was looking at when I first saw it. I thought it was a normal sync event. When I learned enough about the access patterns to recognize the difference, I went back and found it."

Marcus was quiet, running the implications. Eleven days. The data had been out of the trust boundary for eleven days, and the environment had continued operating as though it hadn't, because nothing in the protocol could detect an authorized peer reading a document they had legitimate access to. The access itself wasn't the violation. The destination was the violation, and the destination was outside the system's visibility.

"I need to verify independently before we involve anyone else," he said. "Can you share the raw annotation data, not the rendered version?"

She shared it. He ran three separate verification passes using tools that had no connection to the project environment. The anomaly held up under all three. The signature was Kenji's. The destination was outside the project's peer network. The volume that had been exported contained everything.

He sat in his sandboxed environment for a moment, the jacaranda trees in his peripheral vision, the project he had spent eight months building suddenly existing in two states simultaneously: the ongoing work and the compromised artifact, occupying the same space, indistinguishable from the outside.

"I'm going to contact Yuki," he said. "She's the project lead. This goes to her first, and then to the organization's security team, and then we follow whatever process they define."

"I know," Priya said. "I just needed someone else to see it first."

"Yes," Marcus said. "That was right."

---

## Part Seven: Removal

The organizational process took four days. It moved faster than Priya had expected and slower than Marcus had hoped. There were interviews, conducted outside the project environment entirely, in a separate secure channel established by the organization's security team. There was documentation — a careful, timestamped record of the anomaly, the verification, the chain of communication — that Marcus wrote with the same precision he brought to his debugging logs, because he understood that this document would matter in ways that extended beyond the project.

At the end of the four days, the conclusion was reached and acted upon. Kenji's employment was terminated. The device hosting his peer node was remotely wiped under the protocol he had agreed to when he joined. His presence zone in the reading room went dark.

The room looked wrong with the dark zone. The floor pattern still showed four presence areas plus the general center, but the north window zone was simply absent, a negative space where a person had been. Yuki noticed it when she arrived for the emergency session she had called for the remaining team. She made a note to herself to reconfigure the presence zones before they resumed normal work. She could not have said exactly why it felt urgent to do that before anything else, but it did.

"We need to talk about what we do next," she said.

The remaining team was present: Yuki, Marcus, Amara, Dmitri, Priya. Five people where there had been six.

"The planning document is compromised," Marcus said. "The sync protocol architecture is compromised. Anything in that Journal volume is outside our trust boundary and has been for eleven days."

"Can we know what was done with it?" Amara asked.

"No," Marcus said. "We can know it left. We can't know where it went."

The room was quiet with the particular quality of quiet that follows a sentence that closes a door.

"Then we operate on the assumption that everything in that volume is known to a third party," Dmitri said, "and we design accordingly."

"Yes," Yuki said. "Which means before we do anything else, we rekey the entire environment." She looked at Marcus. "How long?"

"If we do it correctly?" He considered. "Six hours for the cryptographic work. Another two to verify. We should not rush the verification."

"Then we start now."

---

## Part Eight: Rekeying

Marcus opened his workspace — not the shared reading room, which was temporarily suspended pending the security work, but a private environment that the organization's security team had provisioned for exactly this contingency. It was sparse: a plain surface, no aesthetic, nothing but functional tools. He preferred it that way for this kind of work.

He opened his notes and began drafting the rekeying protocol while the concepts were still sharp in his mind. He would share the documentation with the team as he worked, not because they needed to understand every technical step but because the project's philosophy held that no critical process should exist only in one person's head, and because he believed that principle more firmly now than he had four days ago.

---

*Rekeying Protocol: Oaks Project Environment*
*Author: Marcus O.*
*Status: In progress*

---

**The problem we are solving** has two parts. The first part is forward secrecy: ensuring that Kenji, or whoever now holds the data he exported, cannot use the compromised material to decrypt future communications or access future document versions. The second part is backward integrity: ensuring that the remaining peers can establish a new web of trust that does not include the compromised node, and that the new trust relationships cannot be undermined by anything the compromised node previously held.

These are related but distinct problems, and they require different tools.

---

### Step 1: Rotate all long-term identity keys

Every peer in the project has a long-term keypair — the public key serving as their peer identity, the private key used to sign operations and establish session keys. These long-term keys are the roots of the web of trust. Kenji's public key exists in the ACL of every project document. It must be removed, and the ACL records must be re-signed by the remaining peers to reflect his removal.

But removing his key from the ACL is not sufficient if the remaining peers continue using their existing long-term keys, because Kenji's node previously held copies of those public keys and their associated trust signatures. He knows the full previous trust graph.

The remaining peers must therefore generate entirely new long-term keypairs.

```clojure
(ns nls.security.rekey)

(defn generate-peer-identity []
  (let [keypair (crypto/generate-keypair :ed25519)]
    {:peer-id    (encode-public-key (:public keypair))
     :public-key (:public keypair)
     :private-key (:private keypair)   ;; never leaves this peer
     :created-at (current-lamport-clock)
     :supersedes (:peer-id (current-identity))}))
```

The `:supersedes` field is important: it creates a cryptographically verifiable chain from old identity to new, signed by the old private key before it is retired. This allows the remaining peers to recognize each other's new identities without an out-of-band introduction — each new key carries a signature from the old key, and the remaining peers already trusted the old keys.

Kenji's old key cannot create a valid supersession signature to a new key, because the supersession signature must be accepted by the group, and the group is now the four remaining peers. His old key is in the revocation list. Any supersession chain that passes through a revoked key is invalid regardless of subsequent signatures.

```clojure
(defn supersession-valid? [new-peer-id trust-store revocation-list]
  (let [chain (build-supersession-chain new-peer-id trust-store)]
    (and
      ;; Every link in the chain must be signed by the key it supersedes
      (every? verify-supersession-signature chain)
      ;; No revoked key appears anywhere in the chain
      (not-any? #(contains? revocation-list (:peer-id %)) chain)
      ;; Chain terminates at a key that was trusted before the compromise
      (trusted-at-baseline? (last chain) trust-store))))
```

---

### Step 2: Establish new pairwise session keys with perfect forward secrecy

Long-term identity keys are used for authentication, not for encrypting document data. Document data is encrypted with session keys that are ephemeral — generated fresh for each sync session, derived using a key agreement protocol, and discarded after use. This is what perfect forward secrecy means in practice: even if a long-term key is compromised, session keys derived in the past cannot be reconstructed from it, because they were derived from an ephemeral exchange that no longer exists.

The mechanism is a Diffie-Hellman ratchet — the same underlying construction used in Signal Protocol — adapted for the peer-to-peer multi-party environment:

```clojure
(defn initiate-rekeying-session [local-peer remote-peer-id]
  ;; Generate a fresh ephemeral keypair for this specific rekeying session.
  ;; This keypair is used once and then discarded.
  (let [ephemeral-kp (crypto/generate-keypair :x25519)
        ;; Sign the ephemeral public key with our new long-term key,
        ;; proving we are who we claim to be under the new identity.
        signed-ephemeral (crypto/sign
                           (:public ephemeral-kp)
                           (:private-key (current-identity local-peer)))]
    {:ephemeral-public  (:public ephemeral-kp)
     :ephemeral-private (:private ephemeral-kp)  ;; local only, never transmitted
     :identity-sig      signed-ephemeral
     :new-peer-id       (:peer-id (current-identity local-peer))}))

(defn complete-key-exchange [local-initiation remote-response]
  ;; Verify the remote peer's new identity and ephemeral signature
  (assert (verify-supersession-valid? (:new-peer-id remote-response)))
  (assert (crypto/verify (:ephemeral-public remote-response)
                          (:identity-sig remote-response)
                          (resolve-public-key (:new-peer-id remote-response))))
  ;; Derive the shared session key using both ephemeral keys.
  ;; Neither side transmits this key — both sides compute it independently
  ;; from the exchange. An observer who captured the exchange cannot
  ;; compute the session key without one of the ephemeral private keys,
  ;; both of which are discarded after derivation.
  (let [shared-secret (crypto/dh-exchange
                        (:ephemeral-private local-initiation)
                        (:ephemeral-public remote-response))
        session-key   (crypto/derive-key shared-secret :hkdf-sha256)]
    {:session-key session-key
     :with-peer   (:new-peer-id remote-response)
     :expires-at  (+ (current-time) session-key-lifetime-ms)}))
```

After this exchange, each pair of peers shares a session key that was derived entirely from ephemeral material. Kenji's node has no record of the ephemeral private keys used in these exchanges — they were generated after his node was removed from the trust boundary — and therefore cannot derive the session keys even if he retains the long-term keys he previously held.

---

### Step 3: Re-encrypt the document store

All documents in the Journal are encrypted at rest using keys derived from the peer trust relationships. Since those relationships have changed — one peer removed, all keys rotated — every stored document must be re-encrypted under the new keys.

This is the most operationally expensive step, and it must be done carefully to avoid a window during which documents exist in an intermediate state: decrypted from the old keys but not yet encrypted under the new ones.

The pattern is encrypt-then-swap, never decrypt-in-place:

```clojure
(defn reencrypt-document [doc-id old-key-context new-key-context]
  (let [;; Read and decrypt using old keys — this is the last use of old keys
        plaintext    (journal/read-encrypted doc-id old-key-context)
        ;; Encrypt under new keys — write to a staging location, not the live store
        new-ciphertext (crypto/encrypt plaintext (:document-key new-key-context))
        staging-path  (staging-path-for doc-id)]
    ;; Write to staging
    (journal/write-staging staging-path new-ciphertext new-key-context)
    ;; Verify: decrypt from staging and compare to plaintext
    (let [verified (crypto/decrypt new-ciphertext (:document-key new-key-context))]
      (assert (= plaintext verified) "Re-encryption verification failed"))
    ;; Atomic swap: staging replaces live
    (journal/atomic-swap! doc-id staging-path)
    ;; Securely wipe old ciphertext and staging artifacts
    (secure-wipe! (old-path-for doc-id))
    (secure-wipe! staging-path)))

(defn reencrypt-all-documents [account new-key-context progress-fn]
  (let [doc-ids (journal/all-doc-ids account)]
    (reduce
      (fn [completed doc-id]
        (reencrypt-document doc-id (old-key-context account) new-key-context)
        (progress-fn {:completed (inc completed) :total (count doc-ids)})
        (inc completed))
      0
      doc-ids)))
```

The progress callback is not cosmetic — it feeds a live status display in the rekeying environment so that the team can see exactly where in the document store the process is, and Yuki can make informed decisions if anything needs to be paused or repeated.

---

### Step 4: Rebuild the web of trust without the revoked peer

The web of trust is a set of mutual endorsements — each peer signs a statement saying they consider the other peers legitimate participants. Kenji's endorsements are in the existing web. Simply removing his node from the ACL is insufficient: his endorsements of the remaining peers and their endorsements of him form a subgraph that must be cleanly excised and replaced.

```clojure
(defn rebuild-trust-graph [remaining-peers revocation-list]
  ;; Start from scratch: new trust graph with only the remaining peers' new identities
  (let [new-identities (map :new-peer-id remaining-peers)]
    (reduce
      (fn [trust-graph [peer-a peer-b]]
        ;; Each pair of remaining peers performs a mutual endorsement
        ;; using their new long-term keys
        (let [endorsement-ab (sign-endorsement peer-a peer-b)
              endorsement-ba (sign-endorsement peer-b peer-a)]
          (-> trust-graph
              (add-endorsement endorsement-ab)
              (add-endorsement endorsement-ba))))
      (empty-trust-graph revocation-list)
      (combinations new-identities 2))))

(defn sign-endorsement [endorser-peer endorsed-peer-id]
  {:endorser    (:peer-id (current-identity endorser-peer))
   :endorsed    endorsed-peer-id
   :timestamp   (tick-clock endorser-peer)
   :signature   (crypto/sign
                  (str endorsed-peer-id (tick-clock endorser-peer))
                  (:private-key (current-identity endorser-peer)))})
```

The new trust graph contains no path that passes through Kenji's old or new identity. The revocation list is embedded in the graph structure itself — any future peer attempting to establish trust by presenting a chain that includes the revoked key will be rejected at the `supersession-valid?` check, regardless of how the presentation is constructed.

---

### Step 5: Verify perfect forward secrecy for past sessions

This step cannot undo the export. It cannot protect the document that was exported eleven days ago. What it does is establish a verifiable proof — recorded in the project's security Journal — that all sessions established after the rekeying point have forward secrecy: they used ephemeral keys that no longer exist anywhere, derived from long-term keys that Kenji's node never held.

```clojure
(defn verify-pfs-boundary [rekey-event-id]
  (let [sessions-after (sessions/all-after rekey-event-id)]
    (doseq [session sessions-after]
      (assert (ephemeral-key-used? session)
              (str "Session " (:session-id session) " did not use ephemeral key exchange"))
      (assert (not (key-derivable-from-old-material? session))
              (str "Session " (:session-id session) " may be derivable from pre-rekey material")))
    {:verified-count (count sessions-after)
     :boundary-event rekey-event-id
     :timestamp      (current-time)
     :verifier       (:peer-id (current-identity (local-peer)))}))
```

The verification result is signed by each peer and committed to the security Journal as a permanent record. This is the documentation that says, formally: *everything before this line is potentially known to an adversary; everything after this line is protected by keys that adversary has never held.*

---

Marcus finished the documentation at the same moment he finished the implementation, which was not coincidence — he had written them together, each informing the other, because he had learned long ago that documentation written after the fact describes what you did, while documentation written during describes what you are doing and tends to catch the places where what you are doing does not yet match what you intended.

He ran the verification suite. It passed. He ran it again, because this was the kind of work you ran twice.

Then he shared the protocol document with the team and opened a pull request for the security Journal.

---

## Part Nine: After

The rekeying took eight hours and fourteen minutes. Yuki logged the duration in the project record without comment, because the duration was what it was, and commentary on it would have implied that speed mattered more than correctness, which she did not believe.

The reading room came back online with the new trust parameters at twenty-two hundred Kyoto time, which was inconvenient for Yuki and convenient for no one, which she also noted without complaint. The presence zones had been reconfigured while the environment was suspended. There were five now, arranged differently, without a gap where the sixth had been. Yuki had done this herself, in the suspended environment, before she brought the room back up. She had not mentioned it to anyone. She did not think it required explanation.

Amara arrived first, before anyone else, which was unusual. She stood in the room and looked at the shelves. The security Journal was there now — a new volume, slim, its spine a different color from the project documents, indicating a different document type. It would grow thicker over time if they needed it to, which she hoped they would not.

She looked at the route map.

The map was still there, unchanged. The dotted lines, the quorum points, the careful accumulation of spatial thinking that the team had done over eight months. It had not been compromised — it was a rendering artifact, not a document, generated from data that was now re-encrypted and re-keyed and protected by session keys derived from exchanges that had not existed eleven days ago.

She traced the dotted line from *availability threshold* to *quorum point* with one finger, not touching the surface, just indicating it.

Marcus arrived. He looked tired in the way that people look tired after doing careful, consequential work for eight consecutive hours. He went directly to the board and created a new tile in his presence zone. It was green. It said: *Rekey complete. Verified. PFS boundary established.* Below that, smaller: *Nothing after this line can be read by the compromised node.*

Priya arrived and stood just inside the room with the specific stillness of someone who understood that they had set a consequential thing in motion and were now living in its aftermath. She had not spoken much in the four days since she had sent Marcus that first private message. She had answered every question asked of her, precisely and completely, and had otherwise been quiet in a way that was not withdrawal but was rather the quality of attention she brought to everything.

Yuki noticed it and walked over to her.

"You did the right thing," Yuki said. "I want to say that clearly, while we're all here, because it should be in the room and not just in a private message."

Priya looked at the green tile on Marcus's board. "I almost didn't recognize what I was seeing," she said. "I only knew because I'd spent two weeks in the Journal."

"That's why we have a Journal," Dmitri said. He had arrived without anyone noticing, which was his characteristic mode of presence in the room. He was standing near the archive shelf, a security Journal volume in one hand — rendered as physical, because that was how the environment worked, and because there was something right about holding it. "The Journal is how the project knows what it knows. Including what it should not have lost."

The room held that for a moment.

Then Yuki moved to the center of the room, to the general zone, and created a new note. She addressed it to the team, present and future. It said:

*On this date, the Oaks project environment was rekeyed following a breach of trust by a former member. The technical record of this event is in the security Journal. The human record is simpler: we found it, we fixed it, we continued. The web of trust was rebuilt by the people who remained. It is, if anything, better understood now than it was before — because we had to construct it consciously, rather than inheriting it.*

*The project continues.*

She looked at the note for a moment, then added one more line:

*Priya found it. That matters, and it should be written down.*

---

## Epilogue: The Security Journal

Two years later, a researcher studying the history of distributed collaborative systems came across the Oaks project's published archive — a sanitized version of the Journal, released as a case study in local-first security practices, with identifying information removed and the security event documented in technical detail for the benefit of other teams building similar systems.

The researcher read the rekeying protocol with professional attention, noting the key rotation sequence, the ephemeral exchange construction, the encrypt-then-swap pattern for the document store. These were known techniques, correctly applied. That was not what held her attention.

What held her attention was the note in the general zone. The one that had been written at twenty-two hundred Kyoto time on the night the room came back online. It had been included in the published archive because the team that released it had decided, after discussion, that the technical documentation was incomplete without the human context — that a security event is not only a cryptographic problem but a social one, and that the social record was as important to preserve as the key rotation logs.

The researcher sat with the note for a while.

Then she opened her own project environment — different team, different work, different room — and she went to the general zone and left a note addressed to no one specific and everyone eventual. It said:

*Read the Oaks case study. Particularly the last note. The technical parts are good. The last note is why the technical parts matter.*

The room held it. That was still what rooms were for.

Prompt: Explain how a Kademlia DHT can mitigate a Sybil attack

A Sybil attack is the specific threat where a single adversary creates a large number of fake identities — "Sybil nodes" — to gain disproportionate influence over a distributed network. In a Kademlia DHT, influence is spatial: nodes control the routing and storage of keys that fall near their node ID in the XOR metric space. Flood enough fake IDs into the right neighborhood and you can eclipse legitimate nodes, corrupt lookups, censor content, or surveil traffic. Understanding how Kademlia can resist this requires understanding exactly how Sybil influence works in XOR space first.

## 1. How Sybil attacks exploit Kademlia's structure

Kademlia assigns every node a 160-bit (or 256-bit) ID and measures distance between IDs using XOR — `distance(A, B) = A XOR B`. Routing is purely local: each node only needs to know about nodes in progressively finer neighborhoods of its own ID, organized into k-buckets covering successive powers-of-two distance ranges.

The attack surface this creates is precise: if an adversary can place many nodes with IDs close to a target key K, they can own K's neighborhood. Because Kademlia stores values at the K closest nodes to a key, and because lookups converge toward the closest nodes, an adversary controlling that neighborhood can:

- **Return false values** for lookups of K
- **Drop store requests** silently, making K unreachable
- **Surveil all traffic** flowing toward K
- **Eclipse a legitimate node** by surrounding it with adversarial neighbors, cutting it off from the honest network

The adversary's advantage is that node IDs in a naive Kademlia implementation are self-assigned — a node announces whatever ID it chooses. Generating 10,000 IDs clustered around a target takes milliseconds.

```
Honest network:           After Sybil attack on key K:
                          
  A --- B --- K           A --- S1 --- K
  |     |                 |     |
  C --- D                 S2 -- S3
                          (S1,S2,S3 are Sybil nodes controlled by adversary)
```

## 2. The core mitigation: making node IDs expensive or externally constrained

The root cause of Sybil vulnerability in naive Kademlia is that identity is free. Every mitigation strategy raises the cost of creating a valid identity, either computationally, socially, or cryptographically.

### Cryptographic node IDs: binding identity to a public key

The first and most important mitigation is making a node's ID a deterministic function of its public key, rather than a free choice:

```clojure
(ns nls.dht.identity)

(defn generate-node-id [keypair]
  ;; Node ID is the hash of the public key — cannot be chosen freely.
  ;; Changing your node ID requires generating a new keypair.
  (crypto/sha256 (:public keypair)))

(defn verify-node-id [announced-id public-key]
  ;; Any node can verify that a peer's announced ID matches their key.
  ;; A node claiming an ID it didn't derive from its key is immediately detectable.
  (= announced-id (crypto/sha256 public-key)))
```

This alone doesn't prevent Sybil attacks — generating keypairs is also cheap — but it's a prerequisite for the mitigations that follow, because it makes identity verifiable. Every subsequent mitigation builds on this foundation.

### Proof-of-work on node ID generation

Require that a valid node ID satisfy a difficulty target — similar to Bitcoin's proof-of-work but applied to identity generation rather than block production. The node must find a keypair or nonce such that `H(public_key || nonce)` has a required number of leading zero bits:

```clojure
(defn generate-valid-node-id [difficulty-bits]
  ;; Must find a keypair whose hashed public key meets the difficulty target.
  ;; Expected iterations: 2^difficulty-bits — makes bulk ID generation expensive.
  (loop []
    (let [keypair (crypto/generate-keypair :ed25519)
          candidate-id (crypto/sha256 (:public keypair))]
      (if (meets-difficulty? candidate-id difficulty-bits)
        {:node-id candidate-id :keypair keypair}
        (recur)))))

(defn meets-difficulty? [node-id difficulty-bits]
  (let [id-int (BigInteger. 1 node-id)]
    ;; Check that the leading `difficulty-bits` bits are zero
    (zero? (.shiftRight id-int (- 256 difficulty-bits)))))

(defn verify-pow [node-id public-key difficulty-bits]
  (and (verify-node-id node-id public-key)
       (meets-difficulty? node-id difficulty-bits)))
```

At difficulty 20, generating a single valid ID requires approximately 1 million hash operations — seconds on commodity hardware. Generating 10,000 valid IDs to eclipse a target neighborhood requires roughly 10 billion operations. At difficulty 25, that number becomes 335 billion. The adversary's cost scales linearly with the number of Sybil identities while an honest node pays the cost once.

The tradeoff is that difficulty also costs honest nodes. The right difficulty is calibrated to make bulk Sybil generation economically infeasible while keeping honest node initialization tolerable — typically a few seconds on commodity hardware, which means attacking a neighborhood requires months of compute.

### Geographic or network-topology constraints on IDs

A subtler approach: bind part of the node ID to a verifiable property of the node's network location, such that generating IDs for a specific target neighborhood requires controlling many different IP addresses:

```clojure
(defn generate-ip-constrained-id [ip-address keypair]
  ;; First 32 bits of node ID are derived from IP prefix,
  ;; remaining bits from public key hash.
  ;; Adversary needs many distinct IP ranges to cover arbitrary neighborhoods.
  (let [ip-prefix (ip-to-bits ip-address 32)
        key-hash  (take-bits (crypto/sha256 (:public keypair)) 224)]
    (concat ip-prefix key-hash)))
```

This was proposed by Rowstron and Druschel and is used in some production DHTs. Its limitation is that adversaries with access to large botnets or cloud infrastructure have many IP prefixes available — it raises the cost but does not eliminate the attack.

## 3. Routing table constraints: limiting Sybil influence per bucket

Even if an adversary generates valid IDs, Kademlia's k-bucket structure can be made resistant to flooding by enforcing constraints on how many nodes from the same network neighborhood can occupy a single bucket:

```clojure
(defn bucket-accepts-node? [bucket new-node k]
  (and
    ;; Standard k-bucket size limit
    (< (count (:nodes bucket)) k)
    ;; IP diversity constraint: no more than 1 node per /24 subnet per bucket.
    ;; An adversary controlling one IP range can only contribute 1 node per bucket
    ;; regardless of how many IDs they generate in that range.
    (not-any? #(same-subnet-24? (:ip %) (:ip new-node)) (:nodes bucket))
    ;; Proof-of-work verification: reject IDs that don't meet difficulty
    (verify-pow (:node-id new-node) (:public-key new-node) required-difficulty)))
```

The subnet constraint is particularly effective against adversaries using a single hosting provider: even with thousands of Sybil IDs, each /24 subnet contributes at most one entry per k-bucket, capping the attacker's influence regardless of how many IDs they generate in that address range.

## 4. S/Kademlia: the systematic hardening

S/Kademlia (Baumgart and Meinert, 2007) is the most comprehensive published Sybil-resistant Kademlia variant. It combines several of the above techniques into a coherent security model, and is worth understanding as a reference design:

```clojure
(ns nls.dht.skademlia)

;; S/Kademlia uses two simultaneous PoW puzzles:
;; 1. Static puzzle: solved once at node creation, embedded in node ID
;; 2. Crypto puzzle: solved continuously, proves ongoing CPU commitment
;;    (makes it expensive to maintain many Sybil identities simultaneously,
;;     not just to create them)

(defrecord NodeCertificate [node-id
                             public-key
                             static-nonce   ;; satisfies static PoW
                             dynamic-nonce  ;; satisfies crypto puzzle (time-limited)
                             timestamp
                             signature])    ;; self-signed by private key

(defn valid-certificate? [cert difficulty-static difficulty-dynamic]
  (and
    ;; ID is hash of public key — identity binding
    (verify-node-id (:node-id cert) (:public-key cert))
    ;; Static puzzle: ID itself meets difficulty (one-time cost)
    (meets-difficulty? (:node-id cert) difficulty-static)
    ;; Dynamic puzzle: H(node-id || dynamic-nonce) meets difficulty
    ;; and was generated recently (prevents stockpiling solutions)
    (meets-difficulty?
      (crypto/sha256 (concat (:node-id cert) (:dynamic-nonce cert)))
      difficulty-dynamic)
    (recent-enough? (:timestamp cert))
    ;; Certificate is self-signed — proves key ownership
    (crypto/verify (:node-id cert) (:signature cert) (:public-key cert))))
```

S/Kademlia additionally specifies **disjoint lookup paths**: a lookup for key K sends d parallel queries along d independent paths through the routing table, with no node appearing in more than one path. The lookup accepts the result only if a sufficient fraction of the paths agree:

```clojure
(defn disjoint-lookup [local-node target-key d alpha]
  ;; Launch d parallel lookups on disjoint path sets
  (let [path-sets (partition-routing-table (:routing-table local-node) d)
        results   (pmap (fn [path-set]
                          (lookup-via-path local-node target-key path-set alpha))
                        path-sets)]
    ;; Require agreement across majority of paths — an adversary must
    ;; control nodes on multiple independent paths simultaneously to
    ;; corrupt the result, which requires many more Sybil nodes.
    (if (>= (count-agreeing results) (Math/ceil (/ d 2)))
      (most-common-result results)
      {:status :lookup-failed :reason :path-disagreement})))
```

The security argument: if an adversary controls fraction f of the network, the probability that they control at least one node on every disjoint path drops exponentially as d increases. At d=10 and f=0.2 (20% adversarial nodes — an unrealistically high fraction for a well-maintained network), the probability of corrupting a lookup is less than 0.0001%.

## 5. Social/web-of-trust constraints

For the NLS system specifically — a small team rather than an open public DHT — the most practical mitigation may be the simplest: **closed membership**. New peers must be explicitly invited and their node certificates signed by existing trusted peers before being accepted into the routing table:

```clojure
(defn accept-new-peer? [local-peer new-node-cert trust-store]
  (and
    ;; Technical validity
    (valid-certificate? new-node-cert required-difficulty-static required-difficulty-dynamic)
    ;; Social validity: at least one existing trusted peer has signed
    ;; this node's certificate
    (some (fn [trusted-peer-id]
            (crypto/verify
              (:node-id new-node-cert)
              (get-in new-node-cert [:endorsements trusted-peer-id])
              (resolve-public-key trusted-peer-id trust-store)))
          (keys trust-store))))
```

This is exactly the web-of-trust structure from the rekeying story in Part Eight — each new member enters the network through an explicit endorsement by existing members, making Sybil attacks require compromising an existing trusted peer first (a much harder attack than generating anonymous IDs). The rekeying protocol's removal of Kenji's node is, at the DHT level, precisely a defense against the possibility that he might attempt to rejoin under a new identity or introduce Sybil nodes using credentials derived from his former trust position.

## 6. Why no mitigation is complete

It is worth being honest about the limits. Proof-of-work is vulnerable to adversaries with large computational resources — a well-funded attacker can generate valid IDs faster than the difficulty target assumes. IP constraints are vulnerable to botnets and cloud infrastructure. Web-of-trust constraints are vulnerable to social engineering — compromising a legitimate peer and using their signing key to introduce Sybil nodes, which is exactly what the Kenji scenario represents at the DHT layer.

The realistic security model is not "Sybil attacks are impossible" but "Sybil attacks require resources and access that scale with the strength of the protections, making them economically and practically infeasible for all but the most determined and well-resourced adversaries." For a small team's collaborative tool — which is what the NLS system is — a combination of cryptographic node IDs, modest proof-of-work, and explicit membership endorsement provides a threat model that is appropriate to the actual risk surface.

The deeper point, which connects back to the story: the rekeying after Kenji's breach was effective not primarily because of the cryptographic machinery — though that machinery was necessary — but because the team had maintained a social web of trust that was small enough and well-understood enough that a single anomalous access pattern was detectable by someone who had spent two weeks reading the Journal. In a Kademlia network as in a human organization, the most robust defense against identity-based attacks is knowing, specifically and verifiably, who is supposed to be there.

Prompt: Explain how Ted Nelson's idea of transcopyright is used in this project to provide customers with access to encrypted tree nodes that they have paid for using micropayments.  How does the system create webs of trust with customers who have purchased specific nodes of content?

Ted Nelson's transcopyright concept inverts the traditional model of content ownership. Rather than copying content to distribute it — which severs the connection between the copy and its origin — transcopyright keeps content at its canonical source and grants transient, accountable access to it. The copy never exists independently; what exists is a permission, a payment record, and a live reference. Nelson envisioned this as the foundation of a publishing economy where authors were automatically compensated every time their work was accessed, with the payment infrastructure woven into the reference infrastructure rather than bolted on afterward as DRM.

In the NLS system you have been building, this maps with unusual precision onto the existing architecture: the Journal's content-addressed storage already keeps documents at canonical locations identified by hash; the web-of-trust already provides peer identity; the CRDT operation log already provides an auditable history of who accessed what and when. Transcopyright becomes the economic layer that sits on top of the cryptographic layer, using the same identity and trust machinery for payment authorization that you already use for editing authorization.

## 1. The fundamental model: nodes as independently addressable, purchasable units

In standard OPML and most outline systems, a document is the unit of access — you have the document or you don't. Nelson's insight, and the one that makes transcopyright work technically, is that the tree node is the natural unit of both intellectual content and economic transaction. A single outline node might contain a paragraph of analysis that has value independent of the document containing it. A route map point might reference a piece of research that should compensate its author when accessed. The granularity of payment should match the granularity of the content.

The existing node structure needs one addition — a provenance record that connects the node to its economic identity:

```clojure
(ns nls.transcopyright)

(defrecord ContentNode [node-id          ;; stable UUID — already in your model
                         content-hash     ;; SHA-256 of canonical content — content addressing
                         author-peer-id   ;; the peer who created this node
                         publisher-peer-id ;; may differ from author — licensing relationship
                         price-schedule   ;; map of access-type -> micropayment amount
                         license-type     ;; :transcopyright :open :private
                         canonical-uri    ;; where this node lives at its authoritative source
                         encrypted-content ;; the actual content, encrypted
                         access-key-hash]) ;; hash of the key needed to decrypt — not the key itself

(def access-types
  {:read-once    {:description "Single decryption, no retention"
                  :default-price 0.001}  ;; in whatever micropayment unit
   :session      {:description "Access for duration of one session"
                  :default-price 0.01}
   :permanent    {:description "Permanent local copy authorized"
                  :default-price 0.10}
   :cite         {:description "Right to reference this node from own documents"
                  :default-price 0.05}
   :embed        {:description "Right to transinclude in rendered output"
                  :default-price 0.08}})
```

The `:canonical-uri` field is the direct implementation of Nelson's insistence that content has a home and that transclusion references that home rather than copying from it. When a node is transcluded into another document, the rendering layer fetches from the canonical URI rather than embedding a local copy — which means the author's meter runs every time the content is viewed, not just when it is initially acquired.

## 2. Content-addressed encryption: the node as its own access control

The encryption model needs to be designed so that paying for a node grants access to exactly that node and nothing more — not the whole document, not adjacent nodes, just the purchased unit. This requires per-node encryption keys, which is expensive in key management but correct in terms of access granularity.

The approach that makes this tractable is **content-addressed key derivation**: the decryption key for a node is derived from a combination of the node's content hash and a publisher-held master secret, so the publisher never needs to store per-node keys explicitly — they can re-derive any node's key on demand from its hash:

```clojure
(ns nls.transcopyright.keys)

(defn derive-node-key [master-secret content-hash]
  ;; Key derivation: HKDF with the content hash as the info parameter.
  ;; Same content always produces the same key from the same master secret.
  ;; Publisher can derive any node's key on demand without a key database.
  (crypto/hkdf master-secret
               :info content-hash
               :length 32
               :hash :sha256))

(defn encrypt-node-content [content master-secret]
  (let [content-hash (crypto/sha256 content)
        node-key     (derive-node-key master-secret content-hash)
        iv           (crypto/random-bytes 12)
        ciphertext   (crypto/aes-gcm-encrypt content node-key iv)]
    {:content-hash     content-hash
     :encrypted-content (concat iv ciphertext)
     :access-key-hash  (crypto/sha256 node-key)}))  ;; stored publicly so buyers can verify
                                                      ;; they received the right key after payment

(defn decrypt-node-content [encrypted-node node-key]
  ;; Verify the key is correct before attempting decryption
  (assert (= (:access-key-hash encrypted-node) (crypto/sha256 node-key))
          "Node key does not match access-key-hash — possible fraud or error")
  (let [[iv ciphertext] (split-iv (:encrypted-content encrypted-node))]
    (crypto/aes-gcm-decrypt ciphertext node-key iv)))
```

The `:access-key-hash` stored on the node is the critical detail: it allows a paying customer to verify, after receiving the key, that they were given the correct key for the content they paid for — without the publisher being able to claim they provided the key when they didn't, or the customer being able to claim they didn't receive it when they did. It's a cryptographic receipt, built into the content structure.

## 3. Micropayment channels: paying per node without per-transaction overhead

Paying for each node access with an on-chain blockchain transaction would be economically absurd — the transaction fees would dwarf the payment amounts. Nelson always understood this and envisioned a micropayment infrastructure that was cheap enough to make per-paragraph payments practical. The modern implementation is a **payment channel**: open one on-chain transaction to establish a channel between customer and publisher, then exchange signed payment authorizations off-chain for each node access, settling the accumulated balance periodically.

```clojure
(ns nls.transcopyright.payment)

(defrecord PaymentChannel [channel-id
                            customer-peer-id
                            publisher-peer-id
                            opening-balance     ;; customer's deposit
                            spent-balance       ;; accumulated payments, updated off-chain
                            channel-expiry      ;; Lamport timestamp after which channel closes
                            customer-sig        ;; customer's signature on current spent-balance
                            publisher-sig])     ;; publisher's acknowledgment

(defrecord PaymentAuthorization [auth-id
                                  channel-id
                                  node-id
                                  access-type
                                  amount
                                  new-total-spent  ;; cumulative, to prevent replay
                                  timestamp
                                  customer-sig])   ;; signed by customer's private key

(defn authorize-payment [channel node-id access-type customer-keypair]
  (let [amount      (get-in access-types [access-type :default-price])
        new-total   (+ (:spent-balance channel) amount)
        auth        (->PaymentAuthorization
                      (new-id)
                      (:channel-id channel)
                      node-id
                      access-type
                      amount
                      new-total
                      (current-time)
                      nil)]
    (assoc auth :customer-sig
           (crypto/sign (authorization-bytes auth) (:private-key customer-keypair)))))

(defn verify-authorization [auth channel publisher-keypair]
  (and
    ;; Signature is valid — customer actually authorized this payment
    (crypto/verify
      (authorization-bytes auth)
      (:customer-sig auth)
      (resolve-public-key (:customer-peer-id channel)))
    ;; Amount matches price schedule — no underpayment
    (= (:amount auth)
       (get-in access-types [(:access-type auth) :default-price]))
    ;; Cumulative total is consistent — no replay attack
    (= (:new-total-spent auth)
       (+ (:spent-balance channel) (:amount auth)))
    ;; Channel has sufficient balance
    (<= (:new-total-spent auth) (:opening-balance channel))))
```

The publisher verifies the authorization and, if valid, releases the node key. The key release and the payment authorization are atomically linked — neither party can claim the other didn't perform their side:

```clojure
(defn atomic-key-release [auth channel master-secret]
  ;; Only called after verify-authorization passes
  (let [node-key (derive-node-key master-secret
                                   (:content-hash (get-node (:node-id auth))))]
    ;; Update channel state
    (update-channel! channel (:new-total-spent auth))
    ;; Return key delivery receipt — signed by publisher,
    ;; proves they released the correct key for this authorization
    {:node-key     node-key
     :delivery-receipt
     (crypto/sign
       (concat (authorization-bytes auth) node-key)
       (:private-key (publisher-keypair)))}))
```

The `:delivery-receipt` is the publisher's signed acknowledgment that they provided the correct key in exchange for the payment authorization. Combined with the `:access-key-hash` on the node, this creates a complete, verifiable record: customer authorized payment, publisher delivered key, key was correct for the content. Neither party can defraud the other without producing a cryptographic contradiction.

## 4. Building customer webs of trust from purchase history

Each completed purchase creates a verifiable record that a specific customer peer accessed a specific content node at a specific time for a specific access type. This purchase history is the raw material for a new kind of trust relationship — one based not on social endorsement (which is how the team's peer trust was established) but on demonstrated economic commitment to specific content.

```clojure
(ns nls.transcopyright.trust)

(defrecord PurchaseRecord [record-id
                            customer-peer-id
                            node-id
                            content-hash
                            access-type
                            amount-paid
                            authorization-id    ;; links to PaymentAuthorization
                            delivery-receipt    ;; links to publisher's signed key release
                            timestamp])

(defrecord CustomerTrustProfile [customer-peer-id
                                  public-key
                                  purchase-history    ;; vector of PurchaseRecord
                                  trusted-content     ;; set of node-ids with active access
                                  citation-network    ;; nodes this customer has cited
                                  access-key-cache])  ;; locally held keys for purchased nodes
```

The trust model is content-specific rather than global. A customer who has purchased fifty nodes from a particular author has demonstrated sustained engagement with that author's work — a different kind of trust signal than a key-signing endorsement, but a real one. The system can use this to construct a **content-specific trust web** where access rights flow along citation and purchase relationships:

```clojure
(defn content-trust-score [customer-peer-id node-id purchase-registry]
  ;; How much does this customer's purchase history suggest they should
  ;; be trusted with related content?
  (let [profile     (get-profile purchase-registry customer-peer-id)
        node        (get-node node-id)
        author-id   (:author-peer-id node)
        ;; Direct purchase: highest trust signal
        direct      (some #(= (:node-id %) node-id) (:purchase-history profile))
        ;; Same author: moderate signal — established relationship
        same-author (count (filter #(= (author-of (:node-id %)) author-id)
                                    (:purchase-history profile)))
        ;; Citation relationship: this customer has cited this node from their own work
        cited       (contains? (:citation-network profile) node-id)]
    (cond-> 0
      direct      (+ 100)
      cited       (+ 50)
      :always     (+ (* same-author 5)))))
```

A high trust score enables access policies that wouldn't be available to anonymous purchasers — preview access, discounted bundles, or the ability to receive update notifications when a purchased node's content changes (which, in the Journal system, means a new version has been saved at the canonical URI).

## 5. Transclusion rendering: the live reference

Nelson's most important technical point about transcopyright is that it enables transclusion — the display of content from its canonical source, not from a copy. When a customer's document transcluding a purchased node is rendered, the rendering layer fetches the current version from the canonical URI and decrypts it using the locally cached access key, rather than displaying a static copy:

```clojure
(ns nls.transcopyright.render)

(defn render-transcluded-node [node-id customer-profile rendering-context]
  (let [node        (fetch-from-canonical-uri node-id)
        access-key  (get-in customer-profile [:access-key-cache node-id])
        access-type (active-access-type customer-profile node-id)]
    (cond
      ;; Customer has a valid cached key for this node
      (and access-key (key-valid-for-access-type? access-key access-type))
      (-> node
          (decrypt-node-content access-key)
          (render-in-context rendering-context)
          (annotate-with-provenance node-id))   ;; always shows canonical source

      ;; Customer has an active payment channel but no cached key
      ;; (e.g. :read-once access already consumed, :session expired)
      (active-channel? customer-profile (:publisher-peer-id node))
      (do
        (let [auth    (authorize-payment
                        (get-channel customer-profile (:publisher-peer-id node))
                        node-id
                        (default-access-type access-types)
                        (:keypair customer-profile))
              result  (atomic-key-release auth (get-channel customer-profile (:publisher-peer-id node))
                                          (publisher-master-secret))]
          (cache-key! customer-profile node-id (:node-key result) access-type)
          (render-transcluded-node node-id customer-profile rendering-context)))

      ;; No access — show placeholder with purchase option
      :else
      (render-purchase-prompt node-id rendering-context))))

(defn annotate-with-provenance [rendered-content node-id]
  ;; Every transcluded node shows its origin — Nelson's principle that
  ;; transclusion never severs the connection to the source.
  ;; In the AR environment this appears as a subtle glyph or overlay.
  (assoc rendered-content
         :provenance {:canonical-uri (canonical-uri-of node-id)
                      :author        (author-name-of node-id)
                      :version       (current-version-of node-id)
                      :access-type   (active-access-type-of node-id)}))
```

The provenance annotation is not optional and not cosmetic — it is the technical implementation of Nelson's insistence that intellectual content always carry its origin. In the AR environment from the story, this manifests as a subtle visual indicator on transcluded content that distinguishes it from locally authored content, lets the reader follow the reference to its source, and confirms that the author has been compensated for this display.

## 6. The purchase record as a Journal entry

Purchase records are committed to the customer's local Journal using the same append-only, content-addressed machinery as document versions — which means the customer's complete content access history is preserved, verifiable, and (selectively) shareable:

```clojure
(defn record-purchase-in-journal [customer-peer purchase-record]
  ;; Purchase records are signed Journal entries — tamper-evident,
  ;; preserving the full economic history of what content this peer
  ;; has paid for and when.
  (journal/append!
    customer-peer
    :purchase-log
    (assoc purchase-record
           :journal-sig
           (crypto/sign
             (pr-str purchase-record)
             (:private-key (current-identity customer-peer))))))
```

The signed Journal entry is the customer's receipt. If a publisher later claims a purchase was not made, the customer can produce the signed authorization and delivery receipt, both committed to their Journal. If the customer claims they purchased access they did not have, the publisher's payment channel records show no corresponding authorization. The audit trail is symmetric and unforgeable.

This also enables a social dimension that Nelson envisioned: a customer can selectively share their purchase history — "I have read and paid for these nodes" — as a form of endorsement. In the web-of-trust framework, a customer vouching for a piece of content by demonstrating they paid for it is a qualitatively different signal than an algorithmic recommendation, because it carries economic skin in the game.

## 7. The web of trust that emerges

The purchase and citation relationships create a three-layer trust topology distinct from the team's cryptographic peer trust:

The first layer is **author-to-content trust**: the author's signature on a node certifies that it was produced by that identity and has not been modified since. This is handled by the existing key infrastructure.

The second layer is **publisher-to-customer trust**: the payment channel establishes a bilateral economic relationship, with the delivery receipt as the binding record. This is new, introduced by the transcopyright layer.

The third layer is **customer-to-content trust**: the purchase history and citation network show which content a customer has engaged with economically, creating a content-specific reputation that is more meaningful for discovery and recommendation than social endorsement alone. A customer who has paid for fifty nodes in a particular area of research and has cited ten of them from their own documents has demonstrated sustained intellectual engagement that the system can use to surface related content, extend preferential pricing, or grant access to unreleased drafts.

Nelson's original vision was of a **docuverse** — a single interconnected space of human knowledge where every piece of content was permanently addressable, every access was compensated, and every connection between ideas was preserved and traceable. The NLS system you have built is a small docuverse: team-scale, cryptographically grounded, with a Journal that preserves every version of every idea and a transcopyright layer that makes the economic relationships between ideas as legible and auditable as the intellectual ones. The web of trust that results is not just a security infrastructure. It is a map of who has found what worth paying for, and that map is itself a form of collective knowledge.

Prompt: When a customer purchases content, can they access it in a local-first manner when disconnected from the internet, on the devices where it was securely delivered?

Yes — and local-first access for purchased content is not just a convenience feature, it is a requirement for the transcopyright model to be honest about what customers are actually buying. If purchased content is only accessible when connected to the publisher's server, customers are not buying content — they are renting access, which is a fundamentally different economic relationship that Nelson explicitly wanted to avoid. The whole point of transcopyright is that the payment is a one-time transaction that permanently authorizes access, not a subscription that lapses when the server is unreachable.

The technical challenge is that the encryption model from the previous section — where the publisher derives node keys from a master secret on demand — assumes the publisher is available to perform that derivation. Offline access requires the customer's device to hold the keys independently, without being able to call home. That's a solvable problem, but it requires careful design to avoid creating a situation where holding the key locally is equivalent to holding an unprotected copy of the content.

## 1. The secure local content store

When a node is purchased and the key is delivered, both the encrypted content and the decryption key need to be stored locally in a way that survives disconnection without compromising the access control model. The local store is not a plain file cache — it is a device-bound encrypted vault where the decryption keys are themselves encrypted under a key that never leaves the device:

```clojure
(ns nls.local.store)

;; The device vault key is derived from hardware-bound entropy
;; combined with the customer's authentication credential.
;; It never leaves the device and is never transmitted anywhere.
(defn derive-vault-key [device-binding customer-credential]
  (crypto/hkdf
    (crypto/sha256 (concat device-binding customer-credential))
    :info (encode-string "nls-vault-key-v1")
    :length 32
    :hash :sha256))

(defrecord LocalContentEntry [node-id
                               content-hash
                               encrypted-content    ;; publisher-encrypted bytes
                               vault-encrypted-key  ;; node key, re-encrypted under vault key
                               access-type
                               purchase-record-id   ;; link to Journal entry
                               cached-at            ;; Lamport timestamp
                               expiry               ;; nil for :permanent, timestamp for :session
                               access-count         ;; for :read-once enforcement
                               device-binding-hash]) ;; hash of device binding used to seal

(defn store-purchased-node! [vault node-key encrypted-node purchase-record access-type]
  (let [vault-key       (derive-vault-key (:device-binding vault)
                                           (:credential vault))
        ;; Re-encrypt the node key under the vault key.
        ;; The publisher's encryption of the content is preserved —
        ;; we are not decrypting and re-encrypting content, only
        ;; wrapping the access key in a device-local envelope.
        vault-encrypted  (crypto/aes-gcm-encrypt node-key vault-key
                                                   (crypto/random-bytes 12))
        entry            (->LocalContentEntry
                           (:node-id encrypted-node)
                           (:content-hash encrypted-node)
                           (:encrypted-content encrypted-node)
                           vault-encrypted
                           access-type
                           (:record-id purchase-record)
                           (current-lamport-clock)
                           (expiry-for access-type)
                           0
                           (crypto/sha256 (:device-binding vault)))]
    (write-to-vault! vault entry)
    (update-journal-entry! purchase-record :local-delivery true)))
```

The important structural decision here: the publisher's encrypted content is stored as-is, not decrypted and re-encrypted. The only thing that changes at local storage time is that the node key gets an additional envelope — the vault encryption — that binds it to this specific device. A raw copy of the vault file without the vault key is useless: the content is still publisher-encrypted, and the node key needed to decrypt it is itself encrypted under a key that requires the correct device hardware and customer credential to derive.

## 2. Device binding: tying keys to hardware

The vault key is derived partly from a device-specific binding — a value that is unique to this hardware and cannot be transferred to another device. This is what makes "securely delivered to the devices where it was purchased" meaningful: the content and keys together only unlock on the device where the purchase was completed.

```clojure
(ns nls.local.device)

(defn get-device-binding []
  ;; Combines multiple hardware-specific values.
  ;; No single value is fully stable across firmware updates,
  ;; so combining several provides robustness while maintaining specificity.
  (let [tpm-key       (tpm/get-endorsement-key)       ;; hardware TPM if available
        cpu-id        (hardware/cpu-identifier)
        storage-id    (hardware/storage-device-id)
        os-install-id (os/installation-identifier)]
    (crypto/sha256
      (concat tpm-key cpu-id storage-id os-install-id))))

(defn binding-valid? [vault]
  ;; Called at vault open time — verifies the current device matches
  ;; the device the vault was created on.
  (= (:device-binding-hash (vault-metadata vault))
     (crypto/sha256 (get-device-binding))))
```

The TPM (Trusted Platform Module) is the strongest form of device binding — modern devices have hardware TPMs that can seal keys such that they are only releasable on the same hardware and only when the system is in a known-good state (measured boot). For devices without a TPM, the multi-value hash provides weaker but still meaningful binding. The system should degrade gracefully:

```clojure
(defn best-available-binding []
  (cond
    (tpm/available?)      (tpm/seal-binding (get-device-binding))
    (secure-enclave/available?) (secure-enclave/bind (get-device-binding))
    :else                 {:type :software-only
                           :binding (get-device-binding)
                           :warning "Hardware binding unavailable — vault is software-protected only"}))
```

The `:warning` on software-only binding is surfaced to the customer during purchase so they understand the security model of their specific device. This is an honest disclosure, not a failure — many devices don't have TPMs, and software-only protection is still meaningfully better than unprotected content.

## 3. Offline access: decrypting without calling home

Once the content and vault-encrypted key are stored locally, offline access is a pure local operation:

```clojure
(ns nls.local.access)

(defn access-node-offline [vault node-id customer-credential]
  (let [entry (get-vault-entry vault node-id)]
    (when (nil? entry)
      (throw (ex-info "Node not in local vault — purchase required"
                       {:node-id node-id :reason :not-purchased})))
    ;; Verify device binding — catches attempts to copy vault to another device
    (when-not (binding-valid? vault)
      (throw (ex-info "Vault opened on wrong device"
                       {:node-id node-id :reason :device-mismatch})))
    ;; Check access type validity
    (check-access-validity! entry)
    ;; Derive vault key from current device binding and credential
    (let [vault-key   (derive-vault-key (get-device-binding) customer-credential)
          node-key    (crypto/aes-gcm-decrypt (:vault-encrypted-key entry) vault-key)
          plaintext   (decrypt-node-content entry node-key)]
      ;; Record local access in the Journal — even offline, the audit trail continues.
      ;; This will sync to the network when connectivity is restored.
      (record-local-access! vault entry)
      plaintext)))

(defn check-access-validity! [entry]
  (case (:access-type entry)
    :read-once
    (when (> (:access-count entry) 0)
      (throw (ex-info "Read-once access already consumed"
                       {:node-id (:node-id entry) :reason :access-exhausted})))

    :session
    (when (and (:expiry entry) (> (current-time) (:expiry entry)))
      (throw (ex-info "Session access has expired"
                       {:node-id (:node-id entry) :reason :session-expired})))

    :permanent nil   ;; no validity check needed — permanent is permanent

    :cite nil        ;; citation rights don't expire

    :embed nil))     ;; embed rights don't expire
```

The access count and expiry checks are enforced locally — no server needed. For `:read-once` access, the local vault records the consumption immediately, before even attempting decryption, so a crash during decryption doesn't allow a second attempt. For `:session` access, the expiry is a Lamport timestamp set at purchase time that the local clock can evaluate without network contact.

## 4. Multi-device access: the delivery problem

A customer who purchases on their laptop reasonably expects to also read on their phone. This is the hardest problem in offline-first content access, because every approach involves a tradeoff between security and convenience.

The architecturally cleanest approach is a **secure local transfer protocol** — the customer's devices form their own private peer network, and purchased content is transferred between them through a direct encrypted channel that never passes through the publisher:

```clojure
(ns nls.local.multidevice)

;; Customer's devices form a personal trust domain — separate from
;; the project team's trust domain, managed entirely by the customer.
(defrecord PersonalDevice [device-id       ;; derived from hardware binding
                            device-name
                            public-key      ;; per-device keypair
                            owner-peer-id   ;; customer's primary peer identity
                            authorized-at   ;; when this device was added to personal domain
                            authorizing-device-id]) ;; which existing device authorized this one

(defn authorize-new-device [existing-device new-device-public-key device-name customer-credential]
  ;; An existing authorized device authorizes a new one.
  ;; The chain of authorization is signed — you can always trace how
  ;; a device came to be authorized.
  (let [new-device (->PersonalDevice
                     (derive-device-id new-device-public-key)
                     device-name
                     new-device-public-key
                     (:owner-peer-id existing-device)
                     (current-lamport-clock)
                     (:device-id existing-device))
        auth-sig   (crypto/sign
                     (device-auth-bytes new-device)
                     (device-private-key existing-device customer-credential))]
    (assoc new-device :authorization-sig auth-sig)))

(defn transfer-purchased-node [source-device target-device node-id customer-credential]
  ;; Transfer is only valid between devices in the same personal domain.
  (assert (same-owner? source-device target-device)
          "Cannot transfer between devices with different owners")
  (assert (device-authorized? target-device)
          "Target device not authorized in personal domain")
  ;; Establish a direct encrypted channel between the two devices.
  ;; This uses the same ephemeral key exchange as the peer sync protocol
  ;; but scoped to the personal device domain.
  (let [session     (establish-device-session source-device target-device)
        entry       (get-vault-entry source-device node-id)
        ;; Re-wrap the node key for the target device's vault key.
        ;; We decrypt the vault-encrypted key on the source device,
        ;; immediately re-encrypt it for the target device.
        ;; The node key exists in plaintext for microseconds, in memory only.
        source-vk   (derive-vault-key (device-binding source-device) customer-credential)
        node-key    (crypto/aes-gcm-decrypt (:vault-encrypted-key entry) source-vk)
        target-vk   (derive-vault-key (device-binding target-device) customer-credential)
        rewrapped   (crypto/aes-gcm-encrypt node-key target-vk (crypto/random-bytes 12))]
    ;; Ship the encrypted content (already publisher-encrypted — no change)
    ;; and the target-device-wrapped key over the device session channel.
    (send-over-session session
                        {:encrypted-content (:encrypted-content entry)
                         :vault-encrypted-key rewrapped
                         :purchase-record-id (:purchase-record-id entry)
                         :access-type (:access-type entry)
                         :transfer-sig (sign-transfer source-device node-id target-device)})))
```

The `:transfer-sig` is important: it creates a verifiable record that this specific device authorized the transfer to that specific other device, at this specific time, for this specific node. The publisher's delivery receipt and the customer's transfer chain together create a complete custody record — who authorized what access, to which device, when.

## 5. Access type semantics across devices

Different access types have different device-transfer semantics, and the system should enforce these consistently:

```clojure
(defn transfer-permitted? [entry target-device purchased-device-count]
  (case (:access-type entry)
    ;; Permanent access: customer purchased a permanent right.
    ;; Reasonable policy: allow up to N personal devices simultaneously.
    ;; Nelson's model would say permanent means permanent, everywhere —
    ;; but practical abuse prevention limits simultaneous device count.
    :permanent
    (< purchased-device-count max-personal-devices)

    ;; Read-once: non-transferable by definition.
    ;; Once consumed on any device, the purchase is exhausted everywhere.
    :read-once false

    ;; Session: transfer permitted but session clock is shared,
    ;; not reset — the expiry was set at purchase, not at first access.
    ;; This prevents purchasing a session on device A, letting it expire,
    ;; then "transferring" to device B to get a fresh session.
    :session (not (expired? entry))

    ;; Citation and embed rights: fully transferable —
    ;; they govern what you can do with content in your documents,
    ;; not how many times you can read it.
    :cite true
    :embed true))
```

## 6. Offline Journal sync: maintaining the audit trail while disconnected

When content is accessed offline, the access events still need to be recorded — both for the customer's own records and for the publisher's audit trail. These records accumulate locally and sync when connectivity is restored, using the same CRDT operation log used for document sync:

```clojure
(ns nls.local.audit)

(defrecord LocalAccessEvent [event-id
                              node-id
                              device-id
                              access-type
                              timestamp        ;; Lamport clock
                              wall-clock       ;; for human readability, not security
                              access-result    ;; :success :denied :expired
                              offline?         ;; was the network available at access time?
                              peer-sig])       ;; signed by device's key

(defn record-local-access! [vault entry]
  (let [event (->LocalAccessEvent
                (new-id)
                (:node-id entry)
                (:device-id vault)
                (:access-type entry)
                (tick-local-clock vault)
                (System/currentTimeMillis)
                :success
                (not (network-available?))
                nil)]
    (let [signed (assoc event :peer-sig
                        (crypto/sign (pr-str event)
                                      (device-private-key vault)))]
      (append-to-local-journal! vault signed)
      (queue-for-sync! vault signed))))    ;; will sync to publisher when online

(defn sync-access-log-to-publisher [vault publisher-channel]
  ;; When connectivity is restored, send any unsynced access events.
  ;; Publisher can verify these are authentic — signed by the device key
  ;; that appears in the authorized device chain from the original purchase.
  (let [unsynced (get-unsynced-events vault)]
    (doseq [event unsynced]
      (when (send-to-publisher publisher-channel event)
        (mark-synced! vault (:event-id event))))))
```

The publisher receives the synced access log and can verify several things: that access happened on an authorized device (device key traces back to the purchase), that the access type was honored (read-once not accessed twice, sessions not extended), and that the total access pattern is consistent with the purchase record. This maintains the economic integrity of the transcopyright model even during extended offline periods.

## 7. Content freshness and version reconciliation

When a customer comes back online after an offline period, their locally cached content may be outdated — the publisher may have released a new version of a purchased node. The system needs a reconciliation process that checks for updates without requiring the customer to repurchase:

```clojure
(defn reconcile-after-reconnect [vault publisher-peer]
  (let [local-entries   (all-vault-entries vault)
        version-report  (map (fn [entry]
                               {:node-id      (:node-id entry)
                                :local-hash   (:content-hash entry)
                                :access-type  (:access-type entry)})
                              local-entries)
        ;; Send local hashes to publisher — publisher returns which ones
        ;; have newer versions available. No content is transmitted here,
        ;; just hash comparisons — privacy-preserving update check.
        stale-nodes     (check-for-updates publisher-peer version-report)]
    (doseq [stale stale-nodes]
      (case (:access-type (get-vault-entry vault (:node-id stale)))
        ;; Permanent and embed/cite rights include updates — fetch the new version
        ;; using the existing purchase authorization (no new payment needed)
        (:permanent :cite :embed)
        (fetch-update-with-existing-auth vault publisher-peer stale)
        ;; Session and read-once rights don't include updates —
        ;; notify customer that newer content is available if they wish to repurchase
        (:session :read-once)
        (notify-update-available vault (:node-id stale))))))
```

The version-check sends only content hashes to the publisher — not the content itself, not the decryption keys. The publisher can identify stale content without learning anything about how or when the customer accessed it offline. This is a privacy-preserving protocol: the publisher learns "this customer has version V of this node" but not "this customer accessed this node fourteen times on Tuesday."

## 8. What the customer actually owns

The complete picture of what a customer has locally after purchasing permanent access to a node:

- The publisher-encrypted content bytes, stored in the vault
- The node decryption key, wrapped under their device-binding vault key
- The payment authorization they signed, in their Journal
- The publisher's delivery receipt proving the correct key was delivered
- The signed access log entries for every offline access
- The device transfer records if they moved the content to other devices

None of these individually is sufficient to access the content without the device hardware and customer credential. Together, they constitute a complete, verifiable ownership record that the customer can present in any dispute, that syncs back to the network when connectivity returns, and that preserves Nelson's foundational principle: the customer paid for access and has it, unconditionally, on the devices they purchased it for, whether or not the publisher's server is running, whether or not the internet is available, whether or not the project that built this system still exists.

That last condition is the one Nelson cared most about. The docuverse was supposed to outlast any particular publisher or platform. Local-first architecture with device-bound encryption and a content-addressed Journal is the closest practical implementation of that vision that current technology makes possible.

Prompt: Explain how granular statistics about customer usage patterns for purchased content, which they have opted-in to share with the company, are tracked locally on their device, available for the customer to review, and replicated to company peer nodes.

Usage statistics in this system occupy an unusual position: they are generated by the customer's device, owned by the customer (since everything in a local-first system lives locally first), potentially valuable to the publisher for understanding how content is actually used, and sensitive enough that their collection requires explicit, informed consent. The opt-in requirement is not just a legal formality — it is an architectural constraint that shapes the entire data flow, because statistics that are collected without consent are a surveillance system, while statistics that are collected with consent, stored locally first, reviewed by the customer before transmission, and replicated on customer-controlled terms are a collaborative research relationship.

The design goal is to make the customer a genuine participant in the statistics system rather than its subject.

## 1. The local event stream: capturing everything before deciding what to share

The foundation is a local event log that captures usage events unconditionally, for the customer's own benefit, before any decision about sharing is made. This is the local-first principle applied to analytics: the customer's device knows everything, the company knows only what the customer explicitly chooses to share.

```clojure
(ns nls.analytics.local)

(defrecord UsageEvent [event-id
                        event-type      ;; see event taxonomy below
                        node-id         ;; content node involved
                        device-id       ;; which device generated this
                        session-id      ;; groups events within one reading session
                        timestamp       ;; Lamport clock for ordering
                        wall-clock      ;; human-readable time
                        duration-ms     ;; for timed events (reading, viewing)
                        depth-context   ;; outline depth at time of event
                        interaction     ;; what input modality was used
                        local-only?     ;; customer has marked this event never-share
                        shared?])       ;; has this been replicated to company nodes

(def event-taxonomy
  {:content/opened        "Node was decrypted and displayed"
   :content/closed        "Node display ended"
   :content/read-time     "Estimated time spent reading node content"
   :content/scrolled      "Customer scrolled through node content"
   :content/zoomed        "Customer zoomed into specific section"
   :content/cited         "Customer cited this node from their own document"
   :content/embedded      "Customer embedded this node via transclusion"
   :content/bookmarked    "Customer bookmarked this node"
   :content/annotated     "Customer added a personal annotation to this node"
   :content/shared-view   "Customer shared their view of this node in a group session"
   :navigation/arrived-from  "Which node or context preceded this one"
   :navigation/departed-to   "Which node or context followed this one"
   :navigation/jump          "Customer used a link/reference to reach this node"
   :navigation/search        "Customer found this node via search"
   :outline/expanded      "Customer expanded a subtree rooted at this node"
   :outline/collapsed     "Customer collapsed a subtree rooted at this node"
   :outline/depth-change  "Customer changed their view depth setting"
   :graphic/point-visited "Customer's cursor rested on a linked graphic point"
   :session/started       "Reading session began"
   :session/ended         "Reading session ended"
   :session/device        "Which device type and input modality was in use"})
```

Events are captured continuously into the local Journal under a dedicated analytics namespace, using the same append-only, content-addressed machinery used for document versions and purchase records. The analytics Journal is a sibling log, not a separate system.

```clojure
(defn capture-event! [vault event-type node-id context]
  (let [event (->UsageEvent
                (new-id)
                event-type
                node-id
                (:device-id vault)
                (current-session-id vault)
                (tick-local-clock vault)
                (System/currentTimeMillis)
                (duration-if-timed event-type context)
                (:depth (current-cursor context))
                (:input-modality context)
                false    ;; not marked local-only by default
                false)]  ;; not yet shared
    (append-to-analytics-journal! vault event)
    event))
```

The event is written to the local Journal before anything else happens. There is no network call at event capture time, no batching delay, no decision about sharing at this point. The event exists locally and completely, regardless of any subsequent sharing decision.

## 2. Session reconstruction: building meaning from raw events

Raw events are granular but not inherently meaningful. The local analytics layer reconstructs higher-level patterns from the raw event stream, again entirely locally, producing derived statistics that are both more useful and less individually sensitive than the raw events themselves:

```clojure
(ns nls.analytics.sessions)

(defrecord ReadingSession [session-id
                            device-id
                            started-at
                            ended-at
                            duration-ms
                            nodes-visited       ;; ordered sequence of node-ids
                            node-durations      ;; map of node-id -> ms spent
                            navigation-paths    ;; sequences of [from-node to-node reason]
                            depth-profile       ;; histogram of time spent at each outline depth
                            input-modalities    ;; map of modality -> event-count
                            citations-made      ;; nodes cited during this session
                            annotations-made    ;; nodes annotated during this session
                            transclusions-used  ;; nodes reached via transclusion
                            session-type])      ;; :reading :editing :presenting :co-working

(defn reconstruct-session [events session-id]
  (let [session-events (filter #(= (:session-id %) session-id) events)
        sorted         (sort-by :timestamp session-events)]
    (->ReadingSession
      session-id
      (:device-id (first sorted))
      (:wall-clock (first sorted))
      (:wall-clock (last sorted))
      (session-duration sorted)
      (nodes-in-order sorted)
      (time-per-node sorted)
      (navigation-sequences sorted)
      (depth-histogram sorted)
      (modality-counts sorted)
      (citations-from sorted)
      (annotations-from sorted)
      (transclusions-from sorted)
      (infer-session-type sorted))))

(defn time-per-node [events]
  ;; Estimate reading time per node from open/close event pairs.
  ;; Where close events are missing (session ended, tab switched)
  ;; use the next open event as the implicit close.
  (let [pairs (pair-open-close-events events)]
    (into {} (map (fn [[open close]]
                    [(:node-id open)
                     (- (:wall-clock close) (:wall-clock open))])
                  pairs))))

(defn depth-histogram [events]
  ;; How much time did this customer spend at each outline depth?
  ;; Useful for understanding whether they read deeply or skim structure.
  (reduce (fn [hist event]
            (update hist (:depth-context event) (fnil + 0) 1))
          {}
          (filter #(= :content/opened (:event-type %)) events)))
```

The session reconstruction is a pure local computation — no network involved. The customer can inspect their reading sessions directly in their local environment, seeing the same data that would potentially be shared with the publisher, before deciding whether to share it.

## 3. The opt-in interface: granular consent, not binary

A single "share statistics" checkbox is not meaningful consent for a system this granular. The customer needs to be able to understand specifically what they are sharing and control it at the level of individual event types, time ranges, and content nodes:

```clojure
(ns nls.analytics.consent)

(defrecord ConsentProfile [profile-id
                            customer-peer-id
                            created-at
                            last-modified
                            global-opt-in?       ;; master switch — false means share nothing
                            event-type-consent   ;; map of event-type -> boolean
                            node-consent         ;; map of node-id -> :share/:local-only/:ask
                            time-range-consent   ;; list of DateRange records to include/exclude
                            aggregation-level    ;; :raw :session :weekly :monthly
                            retention-limit-days ;; how long company may retain shared data
                            purpose-consent])    ;; map of stated purpose -> boolean

(def consent-purposes
  {:improve-content      "Help authors understand how their content is read"
   :improve-navigation   "Help improve outline navigation and search"
   :recommendations      "Enable personalized content recommendations"
   :pricing-research     "Inform future pricing decisions"
   :aggregate-research   "Contribute to anonymized research publications"})

(defn default-consent-profile [customer-peer-id]
  ;; Default is share nothing — opt-in must be explicit.
  (->ConsentProfile
    (new-id)
    customer-peer-id
    (current-lamport-clock)
    (current-lamport-clock)
    false      ;; global opt-in off by default
    (into {} (map #(vector % false) (keys event-taxonomy)))
    {}         ;; no per-node settings — defaults to global
    []         ;; no time range restrictions
    :session   ;; if they do share, default to session-level aggregation not raw events
    90         ;; 90-day retention limit by default
    (into {} (map #(vector % false) (keys consent-purposes)))))
```

The consent profile is itself a Journal entry — versioned, timestamped, and auditable. If the customer changes their consent settings, the old settings are preserved in the Journal history, so there is a complete record of what was consented to when. This matters both for the customer (they can see exactly what they agreed to at any point in the past) and for the company (they can demonstrate that data was collected under valid consent at the time of collection).

```clojure
(defn update-consent! [vault new-consent-settings]
  (let [current  (current-consent-profile vault)
        updated  (merge current new-consent-settings
                         {:last-modified (current-lamport-clock)})
        change   {:previous-profile-id (:profile-id current)
                  :changes (diff-consent current updated)
                  :changed-at (current-lamport-clock)
                  :change-sig (crypto/sign (pr-str updated)
                                            (device-private-key vault))}]
    (append-to-analytics-journal! vault updated)
    (append-to-analytics-journal! vault change)
    updated))
```

## 4. The local statistics dashboard

The customer's local environment includes a statistics viewer — a first-class part of the NLS reading room, not a hidden settings page — that presents their own usage data in the same outline/graphic format used for content:

```clojure
(ns nls.analytics.dashboard)

(defn generate-local-report [vault time-range]
  (let [events   (events-in-range vault time-range)
        sessions (map #(reconstruct-session events %) (session-ids events))]
    {:summary
     {:total-sessions        (count sessions)
      :total-reading-time-ms (apply + (map :duration-ms sessions))
      :nodes-accessed        (count (distinct (mapcat :nodes-visited sessions)))
      :most-read-nodes       (top-n-by-time sessions 10)
      :navigation-patterns   (common-paths sessions)
      :depth-preference      (aggregate-depth-profile sessions)
      :input-modalities      (aggregate-modalities sessions)
      :citation-frequency    (citation-rate sessions)
      :peak-usage-times      (usage-histogram sessions :hour-of-day)}
     :sessions sessions
     :consent-summary
     {:what-would-be-shared  (events-matching-consent vault events)
      :what-stays-local      (events-not-matching-consent vault events)
      :pending-sync          (unsynced-consented-events vault)}}))
```

The consent summary section is the key element: it shows the customer exactly what has already been replicated to company nodes, what is queued for replication, and what will remain local-only, before any replication happens. This is the review step that makes opt-in meaningful rather than theoretical.

The dashboard is rendered as a route map alongside an outline — fitting naturally into the NLS environment. Reading time per node becomes point sizes on the map. Navigation paths become the lines between points. The customer's own intellectual journey through the content is made spatially legible to them, in the same visual language used for the content itself.

## 5. Privacy-preserving aggregation before transmission

Even with explicit consent, transmitting raw events to company nodes is more invasive than necessary for most analytical purposes. The local device can perform aggregation and anonymization before transmission, deriving statistics that answer the publisher's questions without exposing the underlying event stream:

```clojure
(ns nls.analytics.aggregation)

(defn aggregate-for-sharing [events consent-profile]
  (case (:aggregation-level consent-profile)

    :raw
    ;; Customer has explicitly consented to raw event sharing.
    ;; Still filtered by event-type-consent and node-consent.
    (filter-by-consent events consent-profile)

    :session
    ;; Sessions are shared, not individual events.
    ;; Timestamps are quantized to the nearest hour — exact timing not shared.
    (->> (group-by :session-id events)
         (map (fn [[sid evts]] (reconstruct-session evts sid)))
         (filter #(session-consented? % consent-profile))
         (map #(quantize-timestamps % :hour)))

    :weekly
    ;; Only weekly aggregates shared — no individual sessions visible.
    (aggregate-to-weekly events consent-profile)

    :monthly
    ;; Maximum aggregation — only monthly totals.
    (aggregate-to-monthly events consent-profile)))

(defn aggregate-to-weekly [events consent-profile]
  (let [weeks (group-by week-of events)]
    (map (fn [[week week-events]]
           {:week               week
            :consented-events   (filter-by-consent week-events consent-profile)
            :node-read-times    (aggregate-read-times week-events)
            :navigation-summary (summarize-navigation week-events)
            :session-count      (count (distinct (map :session-id week-events)))
            :depth-profile      (depth-histogram week-events)
            :modality-profile   (modality-counts week-events)
            ;; Exact node-ids included only if node-consent allows it
            :nodes-accessed     (consented-node-list week-events consent-profile)})
         weeks)))

(defn k-anonymize [aggregated-events k]
  ;; Ensure no individual reading pattern is unique enough to identify
  ;; a specific customer even after aggregation.
  ;; Any aggregate bucket with fewer than k customers contributing
  ;; is suppressed before transmission.
  (filter #(>= (:contributing-customers %) k) aggregated-events))
```

The k-anonymization step is particularly important for the publisher's aggregate research use case: if a specific reading pattern is so unusual that it would only match one customer, including it in even aggregated reports effectively de-anonymizes that customer. The k threshold is a configurable parameter in the consent profile — customers can choose how much uniqueness protection they want.

## 6. The replication protocol: pushing to company peer nodes

When connectivity is available and unsynced consented events exist, the local device replicates to company peer nodes using the same gossip protocol used for document sync, but with additional consent-verification steps:

```clojure
(ns nls.analytics.replication)

(defrecord AnalyticsPayload [payload-id
                              customer-peer-id
                              device-id
                              consent-profile-id   ;; which consent profile authorized this
                              consent-profile-hash ;; hash of consent profile for verification
                              aggregation-level
                              time-range
                              events               ;; the aggregated/filtered events
                              retention-limit-days ;; from consent profile
                              permitted-purposes   ;; from consent profile
                              payload-sig          ;; signed by customer device
                              created-at])

(defn prepare-analytics-payload [vault consent-profile time-range]
  (let [raw-events   (events-in-range vault time-range)
        aggregated   (aggregate-for-sharing raw-events consent-profile)
        anonymized   (k-anonymize aggregated minimum-k-threshold)
        payload      (->AnalyticsPayload
                       (new-id)
                       (:customer-peer-id vault)
                       (:device-id vault)
                       (:profile-id consent-profile)
                       (crypto/sha256 (pr-str consent-profile))
                       (:aggregation-level consent-profile)
                       time-range
                       anonymized
                       (:retention-limit-days consent-profile)
                       (:purpose-consent consent-profile)
                       nil
                       (current-lamport-clock))]
    (assoc payload :payload-sig
           (crypto/sign (pr-str payload) (device-private-key vault)))))

(defn replicate-to-company-nodes [vault company-peer-ids]
  (let [consent     (current-consent-profile vault)
        unsynced    (unsynced-time-ranges vault consent)]
    (when (and (:global-opt-in? consent) (seq unsynced))
      (doseq [time-range unsynced]
        (let [payload (prepare-analytics-payload vault consent time-range)]
          (doseq [company-peer company-peer-ids]
            (when (reachable? vault company-peer)
              (let [result (send-analytics! company-peer payload)]
                (when (:acknowledged result)
                  (mark-synced! vault time-range company-peer)
                  (record-replication! vault payload result))))))))))
```

The company peer node that receives the payload verifies several things before accepting it:

```clojure
(defn receive-analytics-payload! [company-node payload]
  (and
    ;; Signature is valid — payload came from who it claims
    (crypto/verify
      (pr-str (dissoc payload :payload-sig))
      (:payload-sig payload)
      (resolve-customer-public-key (:customer-peer-id payload)))
    ;; Consent profile hash matches the profile on record
    ;; (customer can't claim consent they didn't give)
    (valid-consent-on-record? company-node
                               (:customer-peer-id payload)
                               (:consent-profile-id payload)
                               (:consent-profile-hash payload))
    ;; Payload contains only event types the consent profile permits
    (events-within-consent? payload (resolve-consent (:consent-profile-id payload)))
    ;; Aggregation level matches consent profile
    (= (:aggregation-level payload)
       (:aggregation-level (resolve-consent (:consent-profile-id payload))))))
```

The consent profile hash is the key verification: the customer's device signs the payload with a hash of the consent profile that authorized it. The company node checks this hash against the consent profile it received from the customer's device (which is itself a signed Journal entry). If someone attempted to send analytics data claiming a more permissive consent profile than the customer actually set, the hash mismatch would detect it.

## 7. The company-side analytics store

On the company's peer nodes, received analytics payloads are stored in a structure that enforces the retention limits and purpose restrictions from the consent profile:

```clojure
(ns nls.analytics.company)

(defrecord CompanyAnalyticsRecord [record-id
                                    payload-id
                                    customer-peer-id
                                    received-at
                                    retention-expires-at   ;; enforced automatically
                                    permitted-purposes
                                    aggregation-level
                                    events
                                    deletion-scheduled?])

(defn store-analytics! [company-node payload]
  (let [record (->CompanyAnalyticsRecord
                 (new-id)
                 (:payload-id payload)
                 (:customer-peer-id payload)
                 (current-lamport-clock)
                 (+ (current-time-ms)
                    (* (:retention-limit-days payload) 86400000))
                 (:permitted-purposes payload)
                 (:aggregation-level payload)
                 (:events payload)
                 false)]
    (write-to-analytics-store! company-node record)
    ;; Schedule automatic deletion at retention limit
    (schedule-deletion! company-node (:record-id record) (:retention-expires-at record))
    ;; Acknowledge receipt to customer device — triggers mark-synced! on their end
    {:acknowledged true
     :record-id    (:record-id record)
     :receipt-sig  (crypto/sign (pr-str record) (company-private-key company-node))}))

(defn enforce-retention-limits! [company-node]
  ;; Runs periodically — automatically deletes records past their retention date.
  ;; Deletion is permanent and recorded in the company audit log.
  (let [expired (filter #(> (current-time-ms) (:retention-expires-at %))
                         (all-analytics-records company-node))]
    (doseq [record expired]
      (secure-delete! company-node (:record-id record))
      (append-to-audit-log! company-node
                              {:event :analytics-deleted
                               :record-id (:record-id record)
                               :customer-peer-id (:customer-peer-id record)
                               :reason :retention-limit-expired
                               :deleted-at (current-lamport-clock)}))))
```

The scheduled deletion and audit log are both enforceable by the customer: since the company's analytics store uses the same Journal structure as everything else in the system, the customer can request a copy of their portion of the company's audit log and verify that their data was deleted when it should have been. This is local-first accountability applied to the company rather than the customer.

## 8. What the company can and cannot derive

The purpose-consent field in the consent profile creates enforceable restrictions on how the company uses the data. These are enforced at the query layer:

```clojure
(defn query-analytics [company-node query purpose]
  (assert (contains? (keys consent-purposes) purpose)
          "Unknown purpose — query rejected")
  ;; Filter to only records where customer consented to this purpose
  (let [permitted-records (filter #(get-in % [:permitted-purposes purpose])
                                   (all-analytics-records company-node))]
    ;; Apply minimum k-anonymity threshold across the result set —
    ;; even if individual records are aggregated, the query result
    ;; must not be traceable to specific customers
    (->> permitted-records
         (apply-query query)
         (ensure-k-anonymity company-node minimum-query-k)
         (record-query-in-audit-log! company-node query purpose))))
```

The audit log of every query run against the analytics store is itself a Journal entry, signed by the company node. If a customer ever wanted to audit how their data was used, they could request the query log entries that touched their records — a right that the system's architecture makes technically feasible rather than just legally promised.

## 9. What the complete system looks like from the customer's perspective

The customer's experience of the statistics system is a readable Journal that they own and control completely. Their local dashboard shows them everything — the raw events, the reconstructed sessions, the aggregates, the navigation patterns, the depth profiles, their citation habits, the spatial shape of how they move through content. This is information about their own intellectual life that has genuine personal value independent of any sharing.

When they choose to share some of it, they can see exactly which events would be included, at what level of aggregation, for which purposes, with what retention limit, before a single byte leaves their device. The replication happens on their terms, in their time, under a consent profile they can update or revoke at any moment — revocation appends a new Journal entry that the company node accepts and acts on, scheduling deletion of the affected records.

The company receives genuine signal about how their content is used — which nodes hold attention, which navigation paths are common, which outline depths customers prefer, which content is cited and embedded and built upon — without receiving a surveillance stream of raw behavioral data. The customer retains full ownership of their reading history. The economics of the transcopyright model are supported by understanding how content is actually valued in use. And the whole system is auditable by both parties, using the same Journal and trust machinery that underlies everything else in the NLS environment.

Nelson's docuverse was supposed to be a place where the relationship between reader and author was transparent, compensated, and accountable in both directions. The statistics layer, designed this way, extends that transparency to include how content is read, not just whether it was paid for — with the reader in control of what that transparency reveals.

Prompt: Imagine that it is 100 years in the future and the Reading Room (the public name of the Oaks Project) has been obsolete for many years, replaced by Holodeck technologies envisioned in Star Trek.  How can the development artifacts of the project (once restricted to company personnel) be archived in an open source manner, and made available for scholarly research?

# The Reading Room Archive
## A Proposal for Perpetual Open Access to the Oaks Project Development Record
### Submitted to the Coalition for Computing Heritage, 2124

---

## Preface: What We Are Preserving and Why It Is Difficult

The Reading Room project operated from 2024 to 2041, when the last active peer node was decommissioned following the migration of its final user community to the immersive spatial computing environments that had by then become the standard substrate for collaborative intellectual work. For seventeen years it served as both a tool and a demonstration of a particular philosophy: that software could embody an ethical position about knowledge, ownership, memory, and human augmentation, and that these positions could be expressed as verifiable, auditable, running code rather than as marketing claims.

The development record of the Reading Room is therefore not merely a technical archive. It is a philosophical document expressed in Clojure, a legal document expressed in cryptographic proofs, an economic experiment expressed in micropayment channel logs, and a social history expressed in seventeen years of pull request discussions, fork resolutions, and the Reading Room's own Journal — which, fittingly, documented its own construction using the tools it was building.

Preserving this record is difficult for reasons that are themselves historically instructive. The Reading Room was designed to be local-first, decentralized, cryptographically sealed, and economically transactive. Every one of these design virtues creates a corresponding archival challenge. The encryption that protected customer privacy now locks researchers out of usage records that would illuminate how the system was actually used. The decentralization that made the system resilient against server failure also means there is no canonical repository, no single authoritative copy, no obvious place to begin. The micropayment channels that compensated authors fairly have long since settled and closed, leaving only signed receipts whose payment network no longer exists. The peer nodes that held the distributed Journal are spread across physical infrastructure that has changed hands multiple times in a century, running on hardware whose operating systems are four or five generations obsolete, using a JVM runtime that requires emulation to execute.

This proposal describes how we intend to address each of these challenges systematically, in a manner that honors the Reading Room's own values — transparency, auditability, human oversight of automated processes — while making its record genuinely accessible to scholars who will study it with tools and conceptual frameworks the original developers could not have anticipated.

---

## Part One: Inventory and Recovery

### 1.1 What exists and where

After eighteen months of recovery work, the Coalition has identified the following classes of artifacts distributed across seventeen primary sources and an estimated forty to sixty secondary sources that have not yet been fully surveyed:

**Primary source: The distributed Journal DAG.** The Reading Room's own Journal is the most complete record of the project's development. Because it was designed as an append-only, content-addressed, replicated structure, multiple independent copies exist on surviving peer nodes, personal storage devices recovered from estates, and two institutional backups created by universities that were early adopters of the system. No two copies are identical — each reflects the replication state of a different peer at a different moment — but they share a common DAG structure that allows them to be merged into a single canonical archive using the same merge machinery the Reading Room used during its operational life.

```clojure
(ns archive.recovery.journal)

;; The first recovery task is merging the seventeen known Journal DAG
;; fragments into a single canonical archive DAG.
;; This uses the Reading Room's own CRDT merge logic, which is
;; fortunately well-documented in the Journal itself.

(defn merge-journal-fragments [fragments]
  (reduce
    (fn [canonical fragment]
      (let [;; Find the common ancestor between the canonical DAG
            ;; and this fragment — the point where they diverged.
            common-ancestor (find-common-ancestor canonical fragment)
            ;; Collect all version nodes in the fragment that are
            ;; not yet in the canonical DAG.
            new-nodes       (nodes-since fragment common-ancestor)
            ;; Verify each node's content hash before adding —
            ;; a century of storage may have introduced corruption.
            verified-nodes  (filter verify-content-hash new-nodes)
            corrupted       (remove verify-content-hash new-nodes)]
        (when (seq corrupted)
          (log-corruption! corrupted fragment))
        (merge-verified-nodes canonical verified-nodes)))
    (first fragments)
    (rest fragments)))

(defn verify-content-hash [node]
  ;; Content-addressed storage means we can always verify integrity —
  ;; one of the Reading Room's design decisions that directly benefits
  ;; archival recovery a century later.
  (= (:content-hash node)
     (crypto/sha256 (:content node))))
```

The content-addressing design decision, made in 2024 for reasons of integrity and deduplication, turns out to be one of the most valuable properties the archive possesses. Every piece of content in the Journal is self-verifying. Corruption is detectable, not silent.

**Primary source: The source code repositories.** The Reading Room's Clojure source code was maintained in a version control system whose format, fortunately, was well-documented and whose recovery tools have been maintained by the open source community continuously since the project's era. Four complete copies of the repository have been recovered, spanning the project's full development history from the initial scaffolding commit in 2024 to the final maintenance release in 2039.

**Primary source: The pull request and discussion archive.** Because the Reading Room stored pull requests as first-class Journal entries, the PR discussions — including the fork resolutions, reviewer comments, and the complete decision trail for every architectural choice — are recoverable from the Journal DAG. This is an unusually rich record: most software projects of the era lost their discussion history when the hosting platforms that stored it were discontinued. The Reading Room's decision to treat pull requests as content within its own system rather than delegating them to an external platform preserved them.

**Primary source: The cryptographic identity records.** The web-of-trust records from the project's operational period are partially recoverable. Long-term keypairs have been recovered for eleven of the fourteen individuals who contributed to the project over its lifetime. Three keypairs are unrecovered — two because the individuals are deceased and their devices unrecoverable, one because the individual has declined to participate in the archive project, a decision the Coalition respects.

**Primary source: The transcopyright payment records.** The payment channel logs — the signed authorizations and delivery receipts from the micropayment system — are recoverable as Journal entries. The payment network they referenced has not operated since 2067, but the cryptographic records of what was paid, by whom, for what content, remain valid as historical documents even though the payment amounts they represent have no current economic meaning.

**Secondary sources under active investigation:** Personal device vaults recovered from estates of former team members; university research archives from institutions that licensed the Reading Room for academic use; corporate backup systems from the three commercial organizations that operated Reading Room deployments; and personal correspondence from developers, archived by their estates, that contains discussion of design decisions that did not make it into the formal Journal.

### 1.2 What is lost

Honest archival practice requires stating clearly what cannot be recovered.

The customer usage statistics collected under the opt-in analytics system are substantially unrecoverable. The consent profiles specified retention limits — most set at 90 days, some at one year — and the company's enforcement of those limits, documented in the audit log, shows that deletion was carried out faithfully. This is a frustrating gap for researchers interested in how the system was actually used, but it is the correct outcome: the customers who shared their data did so under specific retention terms, and those terms were honored. Reconstructing the data would be both technically impossible and ethically wrong.

The private keys held by individual peer nodes are unrecoverable in almost all cases. This means that content encrypted specifically for individual peer communication — session-specific materials, some personal annotations — cannot be decrypted. The encrypted ciphertext exists; the keys do not. This is, again, the correct outcome from a privacy perspective, even though it creates lacunae in the research record.

The real-time interaction logs from the groupware sessions — the actual sequence of keystrokes, chord values, and mouse movements that constituted collaborative editing sessions — were ephemeral by design and were not persisted to the Journal. Researchers interested in the phenomenology of chord-keyset interaction will need to rely on the secondary literature and on reconstructions using period-accurate hardware, which the Coalition's hardware preservation program maintains.

---

## Part Two: Decryption and Access

### 2.1 The structured key disclosure process

The Reading Room's encryption was not designed to be broken. A century of cryptographic progress has not rendered 2024-era elliptic curve cryptography trivial to attack — the key sizes chosen were conservative by the standards of the time, and the algorithms remain secure. Making encrypted content available for research therefore requires obtaining the keys through legitimate means rather than cryptanalytic means.

```clojure
(ns archive.disclosure.keys)

;; Key disclosure requests are themselves archived Journal entries —
;; the disclosure process is documented with the same permanence
;; as the content it unlocks.

(defrecord KeyDisclosureRequest [request-id
                                  requester-id        ;; researcher or institution
                                  target-content      ;; what content they need to decrypt
                                  research-purpose    ;; stated scholarly purpose
                                  irb-approval-id     ;; institutional review board approval
                                  requested-at
                                  disposition         ;; :pending :approved :denied :partial
                                  disclosed-keys      ;; only populated on approval
                                  conditions])        ;; access conditions attached to approval

(defn process-key-disclosure [request key-registry ethics-board]
  (let [;; Check whether the original data subjects (customers, team members)
        ;; or their designated successors have provided consent for disclosure.
        subject-consent  (check-subject-consent request key-registry)
        ;; Check whether the content is past the agreed confidentiality period
        ;; (the Reading Room's employment agreements specified 25 years for
        ;; internal development materials, now long elapsed).
        past-embargo     (past-embargo-period? (:target-content request))
        ;; Check whether the ethics board has approved the research purpose.
        ethics-approved  (ethics-board/approved? ethics-board request)]
    (cond
      ;; Content past embargo, ethics approved: full disclosure
      (and past-embargo ethics-approved)
      (disclose-keys! request key-registry :full)

      ;; Subject consent obtained regardless of embargo: disclose with conditions
      (and subject-consent ethics-approved)
      (disclose-keys! request key-registry :with-consent-conditions)

      ;; Ethics approved but content not past embargo: partial disclosure
      ;; (metadata and structure, not content)
      ethics-approved
      (disclose-keys! request key-registry :metadata-only)

      ;; Otherwise: denial with explanation
      :else
      (deny-with-explanation request subject-consent past-embargo ethics-approved))))
```

The 25-year confidentiality period specified in the original employment agreements has long elapsed for all development materials. The primary remaining restriction is on customer-facing content — usage data, personal annotations, private communications — where the original data subjects or their estates retain interests that the ethics review process must evaluate.

### 2.2 Key recovery from willing participants

Eleven living or estate-represented former team members have participated in the key recovery program. The process for recovering their long-term private keys follows the supersession chain established by the Reading Room's own rekeying protocol — the same machinery used when Kenji's employment was terminated in the original story, now applied in the direction of openness rather than restriction:

```clojure
(defn recover-legacy-key [participant-estate archive-node]
  ;; Estate provides the original private key material — typically recovered
  ;; from encrypted backups using credentials held by estate executors.
  (let [legacy-key      (estate/provide-key participant-estate)
        ;; Verify the key matches the peer-id in the Journal's trust records
        peer-id         (derive-peer-id legacy-key)
        journal-record  (find-peer-in-journal archive-node peer-id)]
    (when journal-record
      ;; Create a disclosure authorization — a new Journal entry that
      ;; permanently records that this key has been disclosed for archival purposes,
      ;; signed by the estate's authorized representative.
      (let [disclosure-auth
            (->KeyDisclosureAuth
              (new-id)
              peer-id
              (:estate-representative-id participant-estate)
              :archival-research
              (current-lamport-clock)
              (crypto/sign
                (str peer-id :archival-research)
                (:estate-signing-key participant-estate)))]
        (archive-node/record-disclosure! archive-node disclosure-auth)
        {:peer-id peer-id :key legacy-key :authorization disclosure-auth}))))
```

The disclosure authorization is itself a permanent Journal entry. Future researchers will be able to see not just the decrypted content but the complete record of how and why it was decrypted — the ethics approval, the estate consent, the disclosure authorization — all in the same auditable structure as the original content.

---

## Part Three: Long-Term Format Preservation

### 3.1 The emulation stack

The Reading Room ran on the JVM, which was executing Clojure 1.12 (the version stable during the project's peak development years). The JVM itself ran on hardware and operating systems that require emulation on current holodeck substrate hardware. The Coalition maintains a verified emulation stack for this purpose:

```clojure
(ns archive.emulation)

;; The emulation stack is itself version-controlled and archived —
;; we are not merely preserving the Reading Room but also preserving
;; the ability to run it, which requires preserving the environment
;; that ran it.

(defrecord EmulationLayer [layer-id
                            emulates          ;; what system this layer emulates
                            host-requires     ;; what the layer itself needs to run
                            verification-hash ;; hash of the emulator binary — ensures authenticity
                            provenance        ;; where this emulator came from
                            known-deviations  ;; documented behavioral differences from original
                            test-suite-id])   ;; test suite that verifies correct emulation

(def reading-room-emulation-stack
  [{:layer :holodeck-substrate
    :emulates :x86-64-linux-2024
    :verification-hash "sha256:a3f8..."
    :known-deviations ["Timing characteristics differ — benchmarks not reproducible"
                        "Hardware RNG replaced with deterministic PRNG for reproducibility"]}
   {:layer :x86-64-linux-2024
    :emulates :jvm-21
    :verification-hash "sha256:7c2d..."
    :known-deviations ["GC pauses not reproduced — memory behavior may differ"]}
   {:layer :jvm-21
    :emulates :clojure-1.12
    :verification-hash "sha256:9e1a..."
    :known-deviations []}
   {:layer :clojure-1.12
    :emulates :reading-room-2031-release
    :verification-hash "sha256:4b7f..."
    :known-deviations ["Quil/Processing graphics require additional display emulation layer"
                        "Network stack replaced with archive-local simulation"
                        "Cryptographic hardware binding replaced with archive-key-service"]}])
```

The known deviations are documented with scholarly precision — future researchers will need to understand which behaviors of the emulated system are authentic reproductions and which are necessary compromises of the emulation environment. Timing characteristics, in particular, cannot be faithfully reproduced: a chord-keyset interaction that took forty milliseconds to process on 2031 hardware will behave differently in emulation, and researchers studying the phenomenology of the input model should be aware of this.

### 3.2 Canonical format translation

For researchers who do not need to run the Reading Room but simply need to read its artifacts, the Coalition provides canonical translations of all archive content into formats designed for century-scale longevity:

```clojure
(ns archive.formats)

(defmulti translate-to-canonical :artifact-type)

(defmethod translate-to-canonical :opml-document [artifact]
  ;; OPML is already XML — translate to a scholarly XML format with
  ;; explicit namespace declarations and embedded provenance metadata.
  {:format      :scholarly-xml-2124
   :content     (opml->scholarly-xml (:content artifact))
   :provenance  (embed-provenance artifact)
   :original    (preserve-original artifact)   ;; original bytes also preserved
   :translation-notes "OPML 2.0 structure faithfully preserved. Link references
                        resolved where target content is in the archive; unresolved
                        links documented in the annotation layer."})

(defmethod translate-to-canonical :route-graphic [artifact]
  ;; Route graphics were Quil/Processing sketches — translate to SVG
  ;; with embedded semantic annotations preserving the node-reference relationships.
  {:format     :annotated-svg-2124
   :content    (graphic->annotated-svg (:content artifact))
   :node-links (preserve-node-references artifact)
   :provenance (embed-provenance artifact)})

(defmethod translate-to-canonical :pull-request [artifact]
  ;; Pull requests are among the most intellectually valuable artifacts —
  ;; they contain the reasoning behind every significant decision.
  {:format      :scholarly-discourse-record
   :content     (pr->discourse-record artifact)
   :fork-record (embedded-fork-history artifact)
   :resolution  (embedded-resolution-record artifact)
   :provenance  (embed-provenance artifact)
   :annotation  "Pull request discussions represent primary sources for
                  understanding the intellectual history of the project's
                  design decisions. Reviewer comments are preserved verbatim
                  where keys are available; encrypted comments are noted
                  as present-but-inaccessible with the reason documented."})

(defmethod translate-to-canonical :journal-version [artifact]
  {:format     :versioned-document-record
   :content    (version->document-record artifact)
   :dag-position (dag-position artifact)      ;; where in the version DAG this sits
   :parents    (parent-versions artifact)
   :children   (child-versions artifact)
   :provenance (embed-provenance artifact)})
```

### 3.3 The provenance embedding standard

Every artifact in the archive carries embedded provenance — a machine-readable record of what it is, where it came from, what transformations it has undergone, and what uncertainties attach to it. This is the archival application of the Reading Room's own principle that content should always carry its origin:

```clojure
(defrecord ArchivalProvenance [artifact-id
                                original-system     ;; "Reading Room 2031-release"
                                original-format     ;; "OPML 2.0"
                                created-at          ;; original creation timestamp
                                recovered-from      ;; which source the artifact came from
                                recovery-date       ;; when it entered the archive
                                recovery-method     ;; how it was recovered
                                transformations     ;; ordered list of transformations applied
                                verification-status ;; :hash-verified :signature-verified
                                                    ;; :unverifiable-source-unavailable
                                uncertainties       ;; documented doubts about authenticity/completeness
                                access-conditions   ;; any restrictions on use
                                related-artifacts   ;; links to related archive items
                                archivists])        ;; who processed this artifact and when
```

The `:uncertainties` field is where archival honesty lives. A Journal version recovered from a single source with a valid content hash is highly reliable. A version recovered from a source whose device clock was demonstrably misconfigured has uncertain timestamps. A pull request comment recovered from a personal email backup rather than the Journal itself has uncertain completeness. These distinctions matter for scholarly use and must be documented rather than papered over.

---

## Part Four: Open Access and Scholarly Infrastructure

### 4.1 The archive as a Reading Room instance

In an act of deliberate historical continuity, the archive itself is organized and navigated using a modernized descendant of the Reading Room's own interface. Scholars access the archive through a holodeck environment that renders the original reading room aesthetic — the dark wood, the high windows, the bookshelves of Journal volumes — while providing century-appropriate navigation tools. The OPML outline structure that organized the Reading Room's documents becomes the navigational structure of the archive.

This is not nostalgia. It is the recognition that the Reading Room's interface embodied specific intellectual positions about how knowledge should be organized and navigated — hierarchical but not rigid, spatially rendered but not decorative, historically deep but immediately accessible — and that experiencing the archive through that interface gives researchers access to something that a flat file repository cannot provide: the phenomenology of working within the system they are studying.

```clojure
(ns archive.interface)

;; The archive interface is itself an OPML document — navigated using
;; the Reading Room's own outline traversal commands, rendered in a
;; holodeck environment that recreates the original reading room.

(def archive-root-outline
  {:text "The Reading Room Archive"
   :children
   [{:text "Development Record 2024-2041"
     :children
     [{:text "Source Code History"
       :node-ref :archive/source-code-dag
       :children (source-code-years)}
      {:text "Design Decisions (Pull Request Archive)"
       :node-ref :archive/pr-archive
       :children (pr-archive-by-year)}
      {:text "Journal Versions"
       :node-ref :archive/journal-dag
       :children (journal-by-period)}
      {:text "Team Communications"
       :node-ref :archive/communications
       :children (communications-by-participant)}]}
    {:text "Operational Record 2024-2041"
     :children
     [{:text "Deployment History"}
      {:text "User Community Documentation"}
      {:text "Incident and Security Records"
       :note "Includes the 2026 security incident. See access conditions."}]}
    {:text "Scholarly Apparatus"
     :children
     [{:text "Finding Aids"}
      {:text "Emulation Environment"}
      {:text "Key Disclosure Registry"}
      {:text "Related Collections"}
      {:text "Research Bibliography"}]}]})
```

### 4.2 Citation and transclusion in scholarly use

The transcopyright model that the Reading Room implemented for commercial content has an elegant application in the scholarly context: researchers citing archive materials can use the archive's own transclusion machinery to reference specific nodes in specific Journal versions, creating citations that are not just pointers to locations but live connections to verified, content-addressed content.

```clojure
(defn create-scholarly-citation [archive-node-id version-id researcher-id]
  ;; A scholarly citation in this system is a transcopyright reference —
  ;; the archive node at a specific version, with full provenance embedded.
  {:citation-id    (new-id)
   :target         {:node-id    archive-node-id
                    :version-id version-id
                    :content-hash (content-hash-of archive-node-id version-id)}
   :access-type    :cite     ;; using the Reading Room's own access type taxonomy
   :cited-by       researcher-id
   :cited-at       (current-lamport-clock)
   :provenance     (full-provenance-of archive-node-id version-id)
   :canonical-uri  (archive-uri archive-node-id version-id)})
```

A researcher citing a specific pull request comment from 2026 receives a citation that includes the content hash of that comment, its position in the Journal DAG, its provenance record, and a live reference to the archive's canonical copy. A century from now, if someone reads that research and wants to verify the citation, the content-addressed reference will either resolve to identical content or the discrepancy will be detectable — unlike a URL, which may have rotted, or a page number, which requires physical access to a specific edition.

### 4.3 The living annotation layer

The archive is not frozen. Scholars who work with the materials are encouraged to contribute annotations — corrections, contextualizations, connections to other collections, translations of technical concepts into current terminology — through a contribution system that uses the Reading Room's own pull request machinery for review:

```clojure
(ns archive.annotations)

(defrecord ScholarlyAnnotation [annotation-id
                                 target-artifact-id
                                 target-version-id
                                 annotator-id
                                 annotator-institution
                                 annotation-type     ;; :correction :context :connection
                                                     ;; :translation :dispute :elaboration
                                 content
                                 evidence            ;; citations supporting the annotation
                                 peer-reviewed?
                                 review-record-id    ;; if peer reviewed, link to review
                                 created-at
                                 annotation-sig])    ;; signed by annotator's scholarly identity

(defn submit-annotation! [archive annotation reviewer-pool]
  ;; Annotations go through the same pull request review process
  ;; as the original project's code changes — the archive's editorial
  ;; process uses the Reading Room's own decision machinery.
  (let [pr (open-pr! archive
                      :annotation-log
                      annotation
                      (str "Annotation: " (:annotation-type annotation)
                           " on " (:target-artifact-id annotation)))]
    (assign-reviewers! pr reviewer-pool)
    pr))
```

The annotation layer is maintained separately from the primary archive — annotations are clearly distinguished from original materials in all rendering contexts, and the archive's provenance records for original materials are never modified by the annotation process. A researcher always knows whether they are reading an original artifact or a scholarly gloss on it.

### 4.4 Federated access and replication

The archive is maintained by the Coalition but replicated to member institutions using — appropriately — the local-first peer replication protocol that the Reading Room itself developed. Any institution that joins the Coalition's archive network holds a complete, independently verifiable copy of the archive. No single institution's failure can result in data loss. The Merkle DAG structure that the Reading Room used for its Journal means that any two copies of the archive can be compared and merged, with discrepancies automatically detected and flagged for human review.

```clojure
(ns archive.federation)

(defn replicate-to-member-institution [archive member-node]
  ;; The replication protocol is the Reading Room's own sync protocol,
  ;; adapted for archival use. Member institutions receive the full archive
  ;; DAG, not just current state — the complete history is replicated.
  (let [member-state  (request-merkle-root member-node)
        archive-root  (merkle-root archive)
        missing-nodes (find-missing-nodes archive member-node)]
    (doseq [node missing-nodes]
      (send-verified-node! member-node node))
    {:synced-nodes   (count missing-nodes)
     :archive-root   archive-root
     :member-root    (request-merkle-root member-node)   ;; should now match
     :verified       (= archive-root (request-merkle-root member-node))}))
```

---

## Epilogue: A Letter to the Archive

*Found in the personal papers of Yuki Tanaka-Morrison, recovered from the estate of her granddaughter. Written approximately 2078, when Yuki was in her late seventies. Donated to the Coalition archive with the estate's blessing. Unencrypted — Yuki had stopped using encryption for personal correspondence sometime in her sixties, having decided, as she noted in an accompanying journal entry, that she had nothing left to hide and time left to be legible.*

---

I have been thinking about the Reading Room again.

Not the technology — the technology is thoroughly obsolete and I have no nostalgia for it specifically, though I understand why the historians find it interesting. I have been thinking about what we were trying to do, which was harder to explain than how we did it and which I am not sure we ever fully explained even to ourselves.

We were trying to build a system that remembered honestly. That kept its own history without editing it. That preserved the shape of disagreement rather than flattening it into a false consensus. The fork was not a failure of the system — the fork was the system working correctly, holding open a space where two understandings of the same thing could coexist until someone had thought carefully enough to resolve them or until it became clear that they could not be resolved and the project had to live with the tension.

I think about Priya, who found the anomaly in the access log because she had spent two weeks reading the Journal and learned how the system thought. You cannot find something in a record you have not read. The record has to exist and someone has to read it. This sounds obvious and is in practice very rare.

We built the Journal because we believed the process of making something was as important as the thing made. The pull requests, the fork resolutions, the slow accumulation of understanding about what the system actually needed to be — all of it mattered. All of it was the work, not the scaffolding around the work.

If the archive succeeds, future researchers will be able to see not just what we built but how we thought while we were building it. They will find the pull request where Marcus explained why the race condition only appeared with three peers and intermittent connectivity, and they will be able to follow the reasoning from that explanation back to the route map with the dotted lines, back to Dmitri on a train watching birch trees. They will find the security incident and the rekeying, and they will be able to read the note I left in the general zone at twenty-two hundred Kyoto time, and they will understand it in the context of everything that led to it, which is the only context in which it means what I intended it to mean.

This is what the archive is for. Not to preserve us — we are not particularly worth preserving — but to preserve the way a group of people thought together about a hard problem over many years, so that other people thinking about hard problems in circumstances we cannot imagine will have a record of one way it can be done.

The Reading Room is gone. The Journal remains. That is exactly what we designed it to do.

---

*Y.T-M.*
*Kyoto, 2078*

*[Archival note: This letter was found handwritten on physical paper — Yuki's granddaughter notes that her grandmother had returned to writing by hand in her later years, describing it in correspondence as "the original local-first technology." It has been digitized with high-resolution imaging and the original physical document is held by the Kyoto Institute for Computing Heritage. The digitization is available in the archive under artifact-id YTM-2078-001. Content hash: sha256:3d9c...]*


