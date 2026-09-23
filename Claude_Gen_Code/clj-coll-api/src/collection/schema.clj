(ns collection.schema
  "Schema for the personal collection inventory.

   Design notes (see conversation for full rationale):
   - :item/current-location is an untyped ref: it may point at a Location
     entity (a room/shelf - fixed infrastructure) OR at another Item
     (a box, a folder - a portable container). This is what lets containers
     fall out of the model for free, with no separate 'container' type.
   - :photo/items is card-many on the item side, so one photo can depict
     several items (a shelf shot) and one item can have several photos.
   - :movement/* entities are the 'library circulation' record: every
     change of :item/current-location is paired with a :movement fact,
     so the full checkout/relocation history is queryable via d/history
     even though we also keep a fast 'current location' pointer.
   - :connection/* entities reify a typed, notable relationship between
     any two entities (e.g. a book chapter and a magazine article) --
     a plain ref attribute can't carry a relationship type or a note,
     so the relationship itself becomes a first-class entity.
   - :connection/type is kept as a plain keyword in this POC for
     simplicity. A production version should make it a ref to a
     :relation-type entity (label + symmetric? flag) so new relationship
     kinds can be added as data instead of schema changes."
  )

(def schema-txn
  [;; --- Items: physical objects, containers, and informational units ---
   {:db/ident       :item/id
    :db/valueType   :db.type/uuid
    :db/cardinality :db.cardinality/one
    :db/unique      :db.unique/identity
    :db/doc         "Stable external identifier for an item."}

   {:db/ident       :item/name
    :db/valueType   :db.type/string
    :db/cardinality :db.cardinality/one}

   {:db/ident       :item/category
    :db/valueType   :db.type/keyword
    :db/cardinality :db.cardinality/one
    :db/doc         "e.g. :magazine :box :camera :book :chapter :article"}

   {:db/ident       :item/current-location
    :db/valueType   :db.type/ref
    :db/cardinality :db.cardinality/one
    :db/doc         "Points at either a Location entity or another Item (a container)."}

   ;; --- Locations: fixed infrastructure, or transient holders (a person, in-transit) ---
   {:db/ident       :location/id
    :db/valueType   :db.type/uuid
    :db/cardinality :db.cardinality/one
    :db/unique      :db.unique/identity}

   {:db/ident       :location/name
    :db/valueType   :db.type/string
    :db/cardinality :db.cardinality/one}

   {:db/ident       :location/type
    :db/valueType   :db.type/keyword
    :db/cardinality :db.cardinality/one
    :db/doc         ":room :shelf :person :external :in-transit"}

   {:db/ident       :location/parent
    :db/valueType   :db.type/ref
    :db/cardinality :db.cardinality/one}

   ;; --- Photos: flexible many-to-many with items ---
   {:db/ident       :photo/id
    :db/valueType   :db.type/uuid
    :db/cardinality :db.cardinality/one
    :db/unique      :db.unique/identity}

   {:db/ident       :photo/uri
    :db/valueType   :db.type/string
    :db/cardinality :db.cardinality/one}

   {:db/ident       :photo/role
    :db/valueType   :db.type/keyword
    :db/cardinality :db.cardinality/one
    :db/doc         ":primary :detail :damage :provenance :packaging"}

   {:db/ident       :photo/items
    :db/valueType   :db.type/ref
    :db/cardinality :db.cardinality/many}

   ;; --- Movements: the checkout / relocation circulation record ---
   {:db/ident       :movement/item
    :db/valueType   :db.type/ref
    :db/cardinality :db.cardinality/one}

   {:db/ident       :movement/from
    :db/valueType   :db.type/ref
    :db/cardinality :db.cardinality/one}

   {:db/ident       :movement/to
    :db/valueType   :db.type/ref
    :db/cardinality :db.cardinality/one}

   {:db/ident       :movement/reason
    :db/valueType   :db.type/keyword
    :db/cardinality :db.cardinality/one
    :db/doc         ":relocated :loaned-out :returned :sold :disposed"}

   {:db/ident       :movement/due-date
    :db/valueType   :db.type/instant
    :db/cardinality :db.cardinality/one}

   {:db/ident       :movement/notes
    :db/valueType   :db.type/string
    :db/cardinality :db.cardinality/one}

   ;; --- Connections: reified, typed relationships between any two entities ---
   {:db/ident       :connection/id
    :db/valueType   :db.type/uuid
    :db/cardinality :db.cardinality/one
    :db/unique      :db.unique/identity}

   {:db/ident       :connection/from
    :db/valueType   :db.type/ref
    :db/cardinality :db.cardinality/one}

   {:db/ident       :connection/to
    :db/valueType   :db.type/ref
    :db/cardinality :db.cardinality/one}

   {:db/ident       :connection/type
    :db/valueType   :db.type/keyword
    :db/cardinality :db.cardinality/one
    :db/doc         "e.g. :references :quotes :inspired-by :same-topic :contradicts"}

   {:db/ident       :connection/note
    :db/valueType   :db.type/string
    :db/cardinality :db.cardinality/one}

   {:db/ident       :connection/confidence
    :db/valueType   :db.type/keyword
    :db/cardinality :db.cardinality/one
    :db/doc         ":certain :probable :speculative"}])
