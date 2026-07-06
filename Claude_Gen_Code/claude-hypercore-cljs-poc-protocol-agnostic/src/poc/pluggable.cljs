(ns poc.pluggable
  "Same terminal demo as before -- peer A appends, peer B receives via
   replication -- except this version's application code depends only
   on app.protocols. Which decentralized (or mock) technology actually
   moves the bytes is a runtime choice, not a compile-time one.

   Run with: npx nbb src/poc/pluggable.cljs [hypercore|mock]
   Defaults to :mock if no argument is given, since that's the one
   guaranteed to run anywhere (no native deps, no network)."
  (:require [app.protocols :as p]
            [app.factory :as factory]
            ["readline" :as readline]))

(defn log [& args]
  (apply js/console.log args))

(defn- backend-kw-from-argv []
  ;; argv layout differs slightly between runners:
  ;; nbb:          [node, nbb-bin, script.cljs, ...user-args]
  ;; node/shadow:  [node, script.js, ...user-args]
  ;; Find whichever argv entry is *this* script and take what follows it,
  ;; rather than hard-coding an index that shifts between runners.
  (let [argv        (js->clj js/process.argv)
        script-idx  (or (some (fn [[i s]] (when (re-find #"\.(cljs|js)$" s) i))
                               (map-indexed vector argv))
                         1)
        user-args   (drop (inc script-idx) argv)]
    (keyword (or (first user-args) "mock"))))

(defn start-repl! [writer]
  (let [rl (.createInterface readline
                              #js {:input js/process.stdin
                                   :output js/process.stdout
                                   :prompt "peer A> "})]
    (log "")
    (log "Type a line and press enter to append it to peer A.")
    (log "Ctrl+D (or Ctrl+C) to quit.")
    (log "")
    (.prompt rl)
    (.on rl "line"
         (fn [line]
           (-> (p/log-append! writer line)
               (.then (fn [new-length]
                        (log (str "  [peer A] appended block " (dec new-length)
                                  " (" new-length " total, "
                                  (p/log-byte-length writer) " bytes)"))
                        (.prompt rl)))
               (.catch (fn [err] (log "  [peer A] append failed:" err) (.prompt rl))))))
    (.on rl "close"
         (fn []
           (log "\nbye")
           ;; Give any in-flight replication (which happens asynchronously,
           ;; deliberately, in the mock backend -- see app.adapters.mock)
           ;; a moment to land before the process exits, rather than
           ;; racing it.
           (js/setTimeout #(js/process.exit 0) 50)))))

(defn wire-up-reader! [reader]
  (p/log-on-append
   reader
   (fn []
     (let [idx (dec (p/log-length reader))]
       (-> (p/log-get reader idx)
           (.then (fn [data]
                    (log (str "  [peer B] <- received block " idx
                              ": \"" data "\""))))
           (.catch (fn [err] (log "  [peer B] read failed:" err))))))))

(defn -main []
  (let [backend-kw (backend-kw-from-argv)
        backend    (factory/create-backend backend-kw)]
    (log (str "Backend: " (p/backend-name backend)))
    (-> (p/backend-create-writer backend)
        (.then
         (fn [writer]
           (log "Peer A ready. address:" (p/log-address writer))
           (-> (p/backend-create-reader backend writer)
               (.then
                (fn [reader]
                  (log "Peer B ready. address:" (p/log-address reader))
                  (p/backend-link! backend writer reader)
                  (log (str "-- replication wired via " (name backend-kw) " --"))
                  (wire-up-reader! reader)
                  (start-repl! writer))))))
        (.catch (fn [err] (log "fatal error:" err) (js/process.exit 1))))))

;; Runs immediately on namespace load under both nbb and (if required
;; directly) shadow-cljs's :node-script target.
(-main)

(defn noop
  "See poc.core/noop -- shadow-cljs's :node-script target needs an
   :init-fn entry point, but -main already ran above at namespace load."
  [& _])
