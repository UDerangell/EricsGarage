(ns app.adapters.hypercore
  "Adapter: implements app.protocols on top of the real hypercore npm
   package. This is the only namespace in the whole app that knows
   hypercore exists."
  (:require ["hypercore" :as HypercoreMod]
            ["random-access-memory" :as RAMMod]
            [app.protocols :as p]))

(def Hypercore (or (.-default HypercoreMod) HypercoreMod))
(def RAM (or (.-default RAMMod) RAMMod))

(defrecord HypercoreLog [core])

(extend-protocol p/PAppendLog
  HypercoreLog
  (log-append! [{:keys [core]} data]
    (.then (.append core data) (fn [_] (.-length core))))
  (log-get [{:keys [core]} idx]
    (.then (.get core idx) (fn [buf] (.toString buf))))
  (log-length [{:keys [core]}] (.-length core))
  (log-byte-length [{:keys [core]}] (.-byteLength core))
  (log-on-append [{:keys [core]} cb] (.on core "append" cb))
  (log-address [{:keys [core]}] (.toString (.-key core) "hex")))

(deftype HypercoreBackend []
  p/PBackend
  (backend-name [_] :hypercore)

  (backend-create-writer [_]
    (let [core (Hypercore. RAM)
          lg   (->HypercoreLog core)]
      (.then (.ready core) (fn [_] lg))))

  (backend-create-reader [_ writer]
    (let [core (Hypercore. RAM (.-key (:core writer)))
          lg   (->HypercoreLog core)]
      (.then (.ready core) (fn [_] lg))))

  (backend-link! [_ writer reader]
    ;; replicate(true)/replicate(false) mark initiator/responder; piping
    ;; the two streams together is standing in for a network transport
    ;; (TCP, Hyperswarm, ...) -- see the README from the earlier POC.
    (let [s1 (.replicate (:core writer) true)
          s2 (.replicate (:core reader) false)]
      (.pipe s1 s2)
      (.pipe s2 s1))))

(defn create []
  (->HypercoreBackend))
