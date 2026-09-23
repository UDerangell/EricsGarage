(ns collection.db
  "Owns the Datomic connection. `conn` is itself an atom (that's Datomic's
   own concurrency mechanism) -- every `transact!` call below mutates it,
   which is what advances the database value returned by `(db)`."
  (:require [datomic.api :as d]))

(def db-uri "datomic:mem://collection")

(defonce conn (atom nil))

(defn init!
  "Creates the in-memory database (idempotent), connects, and (re)loads
   the schema. Call once at startup, or once per test namespace for a
   clean fixture."
  [schema-txn]
  (d/delete-database db-uri)
  (d/create-database db-uri)
  (reset! conn (d/connect db-uri))
  @(d/transact @conn schema-txn)
  @conn)

(defn transact!
  "Runs a transaction and returns the full Datomic transaction result map
   (:db-before :db-after :tx-data :tempids)."
  [txn-data]
  @(d/transact @conn txn-data))

(defn db
  "The current database value (an immutable snapshot)."
  []
  (d/db @conn))
