(ns collection.core
  (:require [collection.db :as db]
            [collection.schema :refer [schema-txn]]
            [collection.api :refer [app]]
            [ring.adapter.jetty :refer [run-jetty]])
  (:gen-class))

(defn -main [& _args]
  (db/init! schema-txn)
  (println "Collection API listening on http://localhost:3000")
  (run-jetty app {:port 3000 :join? true}))
