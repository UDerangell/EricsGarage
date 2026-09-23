(ns collection.api-test
  (:require [midje.sweet :refer :all]
            [ring.mock.request :as mock]
            [cheshire.core :as json]
            [collection.db :as db]
            [collection.schema :refer [schema-txn]]
            [collection.api :refer [app]]))

;; Fresh in-memory database for this test namespace.
(db/init! schema-txn)

(defn json-req [method url data]
  (-> (mock/request method url)
      (mock/content-type "application/json")
      (mock/body (json/generate-string data))))

(defn call [req]
  (let [resp (app req)]
    (update resp :body #(when % (json/parse-string (slurp %) true)))))

;; -----------------------------------------------------------------------
;; Items
;; -----------------------------------------------------------------------

(fact "creating an item returns 201 with the new item's data"
  (let [resp (call (json-req :post "/items"
                              {:name "Amazing Spider-Man #1"
                               :category "magazine"}))]
    (:status resp) => 201
    (get-in resp [:body :item/name]) => "Amazing Spider-Man #1"
    (get-in resp [:body :item/category]) => "magazine"))

(fact "an item can be created directly inside a location"
  (let [loc  (call (json-req :post "/locations" {:name "Office Shelf" :type "shelf"}))
        loc-id (get-in loc [:body :location/id])
        item (call (json-req :post "/items"
                              {:name "Box of Magazines"
                               :category "box"
                               :location-id loc-id}))]
    (:status item) => 201
    (get-in item [:body :item/current-location :location/name]) => "Office Shelf"))

(fact "fetching an unknown item returns 404"
  (let [resp (call (mock/request :get (str "/items/" (java.util.UUID/randomUUID))))]
    (:status resp) => 404))

;; -----------------------------------------------------------------------
;; Containers: an item can live inside another item (a box)
;; -----------------------------------------------------------------------

(fact "an item can be placed inside a box, which is itself just an item"
  (let [box (call (json-req :post "/items" {:name "Comic Box A" :category "box"}))
        box-id (get-in box [:body :item/id])
        mag (call (json-req :post "/items"
                             {:name "X-Men #1"
                              :category "magazine"
                              :location-id box-id}))]
    (get-in mag [:body :item/current-location :item/name]) => "Comic Box A"))

(fact "contents are resolved recursively through nested boxes"
  (let [big   (call (json-req :post "/items" {:name "Big Box" :category "box"}))
        big-id (get-in big [:body :item/id])
        small (call (json-req :post "/items"
                               {:name "Small Box" :category "box" :location-id big-id}))
        small-id (get-in small [:body :item/id])
        _mag  (call (json-req :post "/items"
                               {:name "Old Comic" :category "magazine" :location-id small-id}))
        contents (call (mock/request :get (str "/items/" big-id "/contents")))]
    (:status contents) => 200
    (count (:body contents)) => 2 ; the small box, and the comic inside it
    (set (map :item/name (:body contents))) => #{"Small Box" "Old Comic"}))

;; -----------------------------------------------------------------------
;; Movements: relocate, checkout, checkin
;; -----------------------------------------------------------------------

(fact "checking out an item updates its current location and logs a movement"
  (let [item (call (json-req :post "/items" {:name "Vintage Camera" :category "camera"}))
        item-id (get-in item [:body :item/id])
        friend (call (json-req :post "/locations" {:name "Alex's House" :type "person"}))
        friend-id (get-in friend [:body :location/id])
        checkout (call (json-req :post (str "/items/" item-id "/checkout")
                                  {:to-location-id friend-id
                                   :due-date "2026-10-15T00:00:00Z"
                                   :notes "lending for a photo project"}))]
    (:status checkout) => 200
    (get-in checkout [:body :item/current-location :location/name]) => "Alex's House"
    (let [hist (call (mock/request :get (str "/items/" item-id "/history")))]
      (:status hist) => 200
      (count (:body hist)) => 1)))

(fact "checking an item back in records a second movement and restores its location"
  (let [item (call (json-req :post "/items" {:name "Record Player" :category "electronics"}))
        item-id (get-in item [:body :item/id])
        shelf (call (json-req :post "/locations" {:name "Living Room" :type "room"}))
        shelf-id (get-in shelf [:body :location/id])
        loanee (call (json-req :post "/locations" {:name "Jamie's House" :type "person"}))
        loanee-id (get-in loanee [:body :location/id])]
    ;; put it on the shelf, then loan it out, then bring it back
    (call (json-req :put (str "/items/" item-id "/location") {:to-location-id shelf-id}))
    (call (json-req :post (str "/items/" item-id "/checkout") {:to-location-id loanee-id}))
    (let [checkin (call (json-req :post (str "/items/" item-id "/checkin")
                                   {:to-location-id shelf-id}))]
      (:status checkin) => 200
      (get-in checkin [:body :item/current-location :location/name]) => "Living Room")
    (let [hist (call (mock/request :get (str "/items/" item-id "/history")))]
      (count (:body hist)) => 3)))

(fact "moving to an unknown location returns 400, not a server error"
  (let [item (call (json-req :post "/items" {:name "Lonely Vase" :category "misc"}))
        item-id (get-in item [:body :item/id])
        resp (call (json-req :put (str "/items/" item-id "/location")
                              {:to-location-id (str (java.util.UUID/randomUUID))}))]
    (:status resp) => 400))

;; -----------------------------------------------------------------------
;; Photos
;; -----------------------------------------------------------------------

(fact "a single photo can be linked to more than one item"
  (let [i1 (call (json-req :post "/items" {:name "Item A" :category "misc"}))
        i1-id (get-in i1 [:body :item/id])
        i2 (call (json-req :post "/items" {:name "Item B" :category "misc"}))
        i2-id (get-in i2 [:body :item/id])
        photo (call (json-req :post "/photos"
                               {:uri "s3://bucket/img1.jpg"
                                :role "primary"
                                :item-ids [i1-id i2-id]}))]
    (:status photo) => 201
    (let [p1 (call (mock/request :get (str "/items/" i1-id "/photos")))
          p2 (call (mock/request :get (str "/items/" i2-id "/photos")))]
      (count (:body p1)) => 1
      (count (:body p2)) => 1
      (get-in p1 [:body 0 :photo/uri]) => "s3://bucket/img1.jpg")))

;; -----------------------------------------------------------------------
;; Connections
;; -----------------------------------------------------------------------

(fact "a typed connection links two independent items (e.g. a chapter and an article)"
  (let [chap (call (json-req :post "/items" {:name "Ch. 3: Origins" :category "chapter"}))
        chap-id (get-in chap [:body :item/id])
        art (call (json-req :post "/items" {:name "1978 Interview" :category "article"}))
        art-id (get-in art [:body :item/id])
        conn (call (json-req :post "/connections"
                              {:from-id chap-id
                               :to-id art-id
                               :type "references"
                               :note "footnote 12"
                               :confidence "certain"}))]
    (:status conn) => 201
    (get-in conn [:body :connection/type]) => "references"
    (let [rel-from-chapter (call (mock/request :get (str "/items/" chap-id "/connections")))
          rel-from-article (call (mock/request :get (str "/items/" art-id "/connections")))]
      (count (:body rel-from-chapter)) => 1
      (get-in rel-from-chapter [:body 0 :type]) => "references"
      ;; connections are discoverable from either side, not just the "from" entity
      (count (:body rel-from-article)) => 1)))
