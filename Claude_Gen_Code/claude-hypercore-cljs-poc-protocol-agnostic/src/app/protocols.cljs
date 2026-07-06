(ns app.protocols
  "The abstraction layer. Application/UI code should require only this
   namespace -- never a specific backend (hypercore, hyperdrive, mock,
   ...) directly. Every method returns a JS Promise, chosen as the
   lingua franca because it's native to both CLJS-on-Node (nbb,
   shadow-cljs) and plain JS interop, with no extra async library needed.")

(defprotocol PAppendLog
  "The lowest common denominator every decentralized-log-like backend
   must support: an ordered, appendable sequence of binary/string blocks.
   This mirrors Hypercore's own core API, since Hyperbee and Hyperdrive
   are themselves built on exactly this shape."
  (log-append! [this data]
    "Append data (a string). Returns a Promise resolving to the new
     total length of the log.")
  (log-get [this idx]
    "Returns a Promise resolving to the data stored at idx.")
  (log-length [this]
    "Synchronous: current known number of blocks.")
  (log-byte-length [this]
    "Synchronous: current known total size in bytes.")
  (log-on-append [this cb]
    "Registers cb (no-arg fn), invoked whenever a new block becomes
     available -- whether appended locally or received via replication.")
  (log-address [this]
    "Synchronous: a backend-opaque identity string for this log (a hex
     key, a CID, a URL -- callers should treat it as an opaque token)."))

(defprotocol PBackend
  "A backend factory + replication strategy, bundled together because
   how you create linked peers and how you replicate between them are
   backend-specific, even though the resulting logs all speak
   PAppendLog identically to application code."
  (backend-name [this]
    "Keyword identifying the backend, e.g. :hypercore, :mock.")
  (backend-create-writer [this]
    "Returns a Promise resolving to a new writable PAppendLog.")
  (backend-create-reader [this writer]
    "Given a writer PAppendLog, returns a Promise resolving to a
     read-only PAppendLog addressed at the same underlying data.")
  (backend-link! [this writer reader]
    "Wires up whatever replication mechanism this backend uses so that
     appends to writer eventually become visible to reader. Synchronous
     to call (the resulting replication itself may be async)."))
