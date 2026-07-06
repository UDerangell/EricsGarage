(ns app.adapters.mock
  "Adapter: implements app.protocols with plain Clojure atoms and no
   external library, npm package, network, or native dependency at all.

   This exists so the rest of the application -- and this whole demo --
   can run in environments that can't or shouldn't reach real
   decentralized-storage infrastructure (a sandbox, a CI job, a unit
   test, an offline dev environment) while exercising the exact same
   application code path as the real hypercore adapter.

   It deliberately simulates replication as an async, out-of-band
   event (via setTimeout) rather than a synchronous side effect of
   log-append!, so that application code written against PAppendLog
   can never accidentally rely on replication being instantaneous --
   a bug class that would only show up once you swapped in a real,
   network-latency-bound backend."
  (:require [app.protocols :as p]))

(defrecord MockLog [state])
;; state is an atom of:
;;   {:id       string
;;    :blocks   [string ...]
;;    :watchers [(fn []) ...]
;;    :peer     (atom nil-or-MockLog)}

(defn- notify-watchers! [log]
  (doseq [cb (:watchers @(:state log))]
    (cb)))

(extend-protocol p/PAppendLog
  MockLog
  (log-append! [{:keys [state] :as this} data]
    (js/Promise.
     (fn [resolve _reject]
       (swap! state update :blocks conj data)
       (let [new-length (count (:blocks @state))
             peer-atom  (:peer @state)]
         ;; Simulate network latency for the replication side-effect,
         ;; independent of resolving the append itself -- mirrors how a
         ;; real replicated write resolves locally well before (or well
         ;; after) a remote peer has actually received the block.
         (js/setTimeout
          (fn []
            (when-let [peer @peer-atom]
              (swap! (:state peer) update :blocks conj data)
              (notify-watchers! peer)))
          15)
         (resolve new-length)))))

  (log-get [{:keys [state]} idx]
    (js/Promise.resolve (get (:blocks @state) idx)))

  (log-length [{:keys [state]}]
    (count (:blocks @state)))

  (log-byte-length [{:keys [state]}]
    (reduce + 0 (map count (:blocks @state))))

  (log-on-append [{:keys [state]} cb]
    (swap! state update :watchers conj cb))

  (log-address [{:keys [state]}]
    (str "mock:" (:id @state))))

(defn- fresh-state [id]
  (atom {:id id :blocks [] :watchers [] :peer (atom nil)}))

(deftype MockBackend []
  p/PBackend
  (backend-name [_] :mock)

  (backend-create-writer [_]
    (js/Promise.resolve (->MockLog (fresh-state "peer-a"))))

  (backend-create-reader [_ _writer]
    (js/Promise.resolve (->MockLog (fresh-state "peer-b"))))

  (backend-link! [_ writer reader]
    (reset! (:peer @(:state writer)) reader)
    (reset! (:peer @(:state reader)) writer)))

(defn create []
  (->MockBackend))
