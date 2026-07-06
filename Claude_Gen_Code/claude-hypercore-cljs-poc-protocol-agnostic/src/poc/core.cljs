(ns poc.core
  "Terminal proof-of-concept: two Hypercore peers (A = writer, B = reader)
   talking over the real Hypercore replication protocol.

   Peer A's replication stream is piped directly into Peer B's replication
   stream. That pipe stands in for a network socket -- Hyperswarm (or any
   other transport) would normally sit here, connecting two separate
   machines. The protocol code on either side doesn't know or care whether
   the bytes travelled across a local pipe or the internet, which is the
   point of this demo: it's the actual Hypercore wire protocol, just with
   a very short wire.

   Runs as-is under nbb (`npx nbb src/poc/core.cljs`) and also compiles
   under shadow-cljs (`npx shadow-cljs compile app`) wherever a JVM + Maven
   access is available -- see README."
  (:require ["hypercore" :as HypercoreMod]
            ["random-access-memory" :as RAMMod]
            ["readline" :as readline]))

;; nbb's ESM-based loader and shadow-cljs's CJS interop wrap npm modules
;; slightly differently. This works under both.
(def Hypercore (or (.-default HypercoreMod) HypercoreMod))
(def RAM (or (.-default RAMMod) RAMMod))

(defn log [& args]
  (apply js/console.log args))

(defn key->hex [core]
  (.toString (.-key core) "hex"))

(defn append! [core line]
  (-> (.append core line)
      (.then (fn [_]
               (log (str "  [peer A] appended block " (dec (.-length core))
                         " (" (.-length core) " total, "
                         (.-byteLength core) " bytes)"))))
      (.catch (fn [err] (log "  [peer A] append failed:" err)))))

(defn wire-up-replication! [writer reader]
  ;; replicate(true) marks the "initiator" side of the connection,
  ;; replicate(false) marks the "responder" side. Each call returns a
  ;; duplex stream speaking the Hypercore protocol; piping them together
  ;; is exactly what a network transport would otherwise do for us.
  (let [stream-a (.replicate writer true)
        stream-b (.replicate reader false)]
    (.pipe stream-a stream-b)
    (.pipe stream-b stream-a)
    (log "-- replication streams connected (peer A <-> peer B) --")))

(defn wire-up-reader-listener! [reader]
  (.on reader "append"
       (fn []
         (let [idx (dec (.-length reader))]
           (-> (.get reader idx)
               (.then (fn [data]
                        (log (str "  [peer B] <- received block " idx
                                  ": \"" (.toString data) "\""))))
               (.catch (fn [err] (log "  [peer B] read failed:" err))))))))

(defn start-repl! [writer]
  (let [rl (.createInterface readline
                              #js {:input js/process.stdin
                                   :output js/process.stdout
                                   :prompt "peer A> "})]
    (log "")
    (log "Type a line and press enter to append it to peer A's Hypercore.")
    (log "It will replicate to peer B over the piped protocol stream.")
    (log "Ctrl+D (or Ctrl+C) to quit.")
    (log "")
    (.prompt rl)
    (.on rl "line"
         (fn [line]
           (-> (append! writer line)
               (.then (fn [] (.prompt rl))))))
    (.on rl "close"
         (fn []
           (log "\nbye")
           (js/process.exit 0)))))

(defn main [& _args]
  (let [writer (Hypercore. RAM)]
    (-> (.ready writer)
        (.then
         (fn []
           (log "Peer A (writer) ready.")
           (log "  core key:" (key->hex writer))
           (let [reader (Hypercore. RAM (.-key writer))]
             (-> (.ready reader)
                 (.then
                  (fn []
                    (log "Peer B (reader) ready, opened against peer A's key.")
                    (log "  core key:" (key->hex reader))
                    (wire-up-replication! writer reader)
                    (wire-up-reader-listener! reader)
                    (start-repl! writer)))))))
        (.catch (fn [err] (log "fatal error:" err) (js/process.exit 1))))))

;; Top-level call so this runs the same way whether loaded by nbb
;; (which just executes the file top-to-bottom) or by shadow-cljs.
(main)

(defn noop
  "shadow-cljs's :node-script target requires an :init-fn entry point.
   main already ran above when this namespace loaded, so this is a no-op
   placeholder to satisfy that requirement."
  [& _])
