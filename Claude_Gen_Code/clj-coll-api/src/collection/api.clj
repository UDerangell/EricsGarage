(ns collection.api
  (:require [collection.db :as db]
            [datomic.api :as d]
            [compojure.core :refer [defroutes GET POST PUT]]
            [compojure.route :as route]
            [ring.middleware.json :refer [wrap-json-body wrap-json-response]]
            [ring.middleware.params :refer [wrap-params]]))

;; ---------------------------------------------------------------------
;; Helpers
;; ---------------------------------------------------------------------

(defn response [status body]
  {:status status :headers {} :body body})

(defn uuid [s]
  (try
    (java.util.UUID/fromString s)
    (catch IllegalArgumentException _
      (throw (ex-info (str "Not a valid id: " s) {:id s})))))

(defn parse-instant [s]
  (when s (java.util.Date/from (java.time.Instant/parse s))))

(defn resolve-item
  "Item ids always resolve as items (used for movement subjects, photo
   subjects, and connection endpoints)."
  [id-str]
  [:item/id (uuid id-str)])

(defn eid-exists? [db lookup-ref]
  (try
    (some? (:db/id (d/pull db '[:db/id] lookup-ref)))
    (catch Exception _ false)))

(defn resolve-ref
  "A 'location-id' in a request may name either a Location (fixed
   infrastructure) or an Item acting as a container (a box). Try both
   unique-identity namespaces and use whichever exists."
  [id-str]
  (let [u (uuid id-str)
        as-item [:item/id u]
        as-loc  [:location/id u]]
    (cond
      (eid-exists? (db/db) as-item) as-item
      (eid-exists? (db/db) as-loc)  as-loc
      :else (throw (ex-info "No item or location with that id" {:id id-str})))))

(defn entity-eid [lookup-ref]
  (:db/id (d/pull (db/db) '[:db/id] lookup-ref)))

;; ---------------------------------------------------------------------
;; Pull patterns
;; ---------------------------------------------------------------------

(def item-pull-pattern
  '[:item/id :item/name :item/category
    {:item/current-location [:item/id :item/name :location/id :location/name]}])

(defn pull-item [db lookup-ref]
  (d/pull db item-pull-pattern lookup-ref))

;; ---------------------------------------------------------------------
;; Items
;; ---------------------------------------------------------------------

(defn create-item! [req]
  (let [{:keys [name category location-id]} (:body req)
        item-uuid (java.util.UUID/randomUUID)
        loc-ref   (when location-id (resolve-ref location-id))
        item-data (cond-> {:db/id "new-item"
                            :item/id item-uuid
                            :item/name name
                            :item/category (keyword category)}
                    loc-ref (assoc :item/current-location loc-ref))
        {:keys [db-after]} (db/transact! [item-data])]
    (response 201 (pull-item db-after [:item/id item-uuid]))))

(defn get-item [req]
  (let [item-ref (resolve-item (get-in req [:params :id]))]
    (if (eid-exists? (db/db) item-ref)
      (response 200 (pull-item (db/db) item-ref))
      (response 404 {:error "item not found"}))))

;; ---------------------------------------------------------------------
;; Locations
;; ---------------------------------------------------------------------

(defn create-location! [req]
  (let [{:keys [name type parent-id]} (:body req)
        loc-uuid   (java.util.UUID/randomUUID)
        parent-ref (when parent-id (resolve-ref parent-id))
        data       (cond-> {:db/id "new-loc"
                             :location/id loc-uuid
                             :location/name name
                             :location/type (keyword type)}
                     parent-ref (assoc :location/parent parent-ref))
        {:keys [db-after]} (db/transact! [data])]
    (response 201 (d/pull db-after '[:location/id :location/name :location/type]
                           [:location/id loc-uuid]))))

;; ---------------------------------------------------------------------
;; Movements (relocate / checkout / checkin)
;; ---------------------------------------------------------------------

(defn move-item!
  "Core movement primitive: records a :movement fact and advances
   :item/current-location, in a single transaction. `reason` defaults to
   :relocated; checkout/checkin below are thin wrappers that fix the reason."
  [item-id {:keys [to-location-id reason due-date notes]}]
  (let [item-ref  (resolve-item item-id)
        to-ref    (resolve-ref to-location-id)
        cur       (:item/current-location (d/pull (db/db) '[:item/current-location] item-ref))
        movement  (cond-> {:db/id "movement"
                            :movement/item item-ref
                            :movement/to to-ref
                            :movement/reason (keyword (or reason "relocated"))}
                    cur       (assoc :movement/from (:db/id cur))
                    due-date  (assoc :movement/due-date (parse-instant due-date))
                    notes     (assoc :movement/notes notes))
        update-loc {:db/id item-ref :item/current-location to-ref}
        {:keys [db-after]} (db/transact! [movement update-loc])]
    (pull-item db-after item-ref)))

(defn move-item-handler [req]
  (let [item-id (get-in req [:params :id])]
    (response 200 (move-item! item-id (:body req)))))

(defn checkout-item! [req]
  (let [item-id (get-in req [:params :id])
        body    (assoc (:body req) :reason "loaned-out")]
    (response 200 (move-item! item-id body))))

(defn checkin-item! [req]
  (let [item-id (get-in req [:params :id])
        body    (assoc (:body req) :reason "returned")]
    (response 200 (move-item! item-id body))))

(defn entity-name [db eid]
  (let [e (d/pull db '[:item/name :location/name] eid)]
    (or (:item/name e) (:location/name e))))

(defn item-history [req]
  (let [item-ref (resolve-item (get-in req [:params :id]))
        eid      (entity-eid item-ref)
        hist     (d/history (db/db))
        rows     (d/q '[:find ?loc ?inst
                         :in $ ?item
                         :where
                         [$ ?item :item/current-location ?loc ?tx true]
                         [$ ?tx :db/txInstant ?inst]]
                       hist eid)]
    (response 200
              (->> rows
                   (map (fn [[loc inst]]
                          {:location (entity-name (db/db) loc)
                           :at (str inst)}))
                   (sort-by :at)))))

;; ---------------------------------------------------------------------
;; Containers: recursive contents listing
;; ---------------------------------------------------------------------

(def contents-rules
  '[[(contents ?container ?thing)
     [?thing :item/current-location ?container]]
    [(contents ?container ?thing)
     [?mid :item/current-location ?container]
     (contents ?mid ?thing)]])

(defn item-contents [req]
  (let [item-ref (resolve-item (get-in req [:params :id]))
        eid      (entity-eid item-ref)
        db       (db/db)
        things   (d/q '[:find [?thing ...]
                         :in $ % ?c
                         :where (contents ?c ?thing)]
                       db contents-rules eid)]
    (response 200 (map #(d/pull db '[:item/id :item/name :item/category] %) things))))

;; ---------------------------------------------------------------------
;; Photos
;; ---------------------------------------------------------------------

(defn create-photo! [req]
  (let [{:keys [uri role item-ids]} (:body req)
        photo-uuid (java.util.UUID/randomUUID)
        item-refs  (mapv resolve-item item-ids)
        data       {:db/id "new-photo"
                    :photo/id photo-uuid
                    :photo/uri uri
                    :photo/role (keyword role)
                    :photo/items item-refs}
        {:keys [db-after]} (db/transact! [data])]
    (response 201 (d/pull db-after '[:photo/id :photo/uri :photo/role]
                           [:photo/id photo-uuid]))))

(defn item-photos [req]
  (let [item-ref  (resolve-item (get-in req [:params :id]))
        eid       (entity-eid item-ref)
        db        (db/db)
        photo-ids (d/q '[:find [?p ...] :in $ ?item :where [?p :photo/items ?item]]
                        db eid)]
    (response 200 (map #(d/pull db '[:photo/id :photo/uri :photo/role] %) photo-ids))))

;; ---------------------------------------------------------------------
;; Connections
;; ---------------------------------------------------------------------

(defn create-connection! [req]
  (let [{:keys [from-id to-id type note confidence]} (:body req)
        conn-uuid (java.util.UUID/randomUUID)
        from-ref  (resolve-item from-id)
        to-ref    (resolve-item to-id)
        data      (cond-> {:db/id "new-conn"
                            :connection/id conn-uuid
                            :connection/from from-ref
                            :connection/to to-ref
                            :connection/type (keyword type)}
                    note       (assoc :connection/note note)
                    confidence (assoc :connection/confidence (keyword confidence)))
        {:keys [db-after]} (db/transact! [data])]
    (response 201 (d/pull db-after '[:connection/id :connection/type :connection/note]
                           [:connection/id conn-uuid]))))

(def connected-rules
  '[[(connected ?a ?b ?type)
     [?c :connection/from ?a]
     [?c :connection/to ?b]
     [?c :connection/type ?type]]
    [(connected ?a ?b ?type)
     [?c :connection/from ?b]
     [?c :connection/to ?a]
     [?c :connection/type ?type]]])

(defn item-connections [req]
  (let [item-ref (resolve-item (get-in req [:params :id]))
        eid      (entity-eid item-ref)
        db       (db/db)
        rows     (d/q '[:find ?other ?type
                         :in $ % ?item
                         :where (connected ?item ?other ?type)]
                       db connected-rules eid)]
    (response 200 (map (fn [[other type]]
                          {:item (d/pull db '[:item/id :item/name] other)
                           :type type})
                        rows))))

;; ---------------------------------------------------------------------
;; Routes
;; ---------------------------------------------------------------------

(defroutes app-routes
  (POST "/items" req (create-item! req))
  (GET  "/items/:id" req (get-item req))
  (PUT  "/items/:id/location" req (move-item-handler req))
  (POST "/items/:id/checkout" req (checkout-item! req))
  (POST "/items/:id/checkin" req (checkin-item! req))
  (GET  "/items/:id/history" req (item-history req))
  (GET  "/items/:id/contents" req (item-contents req))
  (GET  "/items/:id/photos" req (item-photos req))
  (GET  "/items/:id/connections" req (item-connections req))

  (POST "/locations" req (create-location! req))
  (POST "/photos" req (create-photo! req))
  (POST "/connections" req (create-connection! req))

  (route/not-found (response 404 {:error "not found"})))

(defn wrap-errors [handler]
  (fn [req]
    (try
      (handler req)
      (catch clojure.lang.ExceptionInfo e
        (response 400 {:error (.getMessage e) :data (ex-data e)}))
      (catch Exception e
        (response 500 {:error (.getMessage e)})))))

(def app
  (-> app-routes
      wrap-errors
      (wrap-json-body {:keywords? true})
      wrap-json-response
      wrap-params))
