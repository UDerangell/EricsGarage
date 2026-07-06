(ns app.factory
  "The one namespace, besides main/UI wiring, allowed to know that more
   than one backend exists. Everything downstream of create-backend
   talks only to app.protocols."
  (:require [app.adapters.hypercore :as hypercore]
            [app.adapters.mock :as mock]))

(defn create-backend
  "backend-kw: :hypercore or :mock (extend here as new adapters are added)."
  [backend-kw]
  (case backend-kw
    :hypercore (hypercore/create)
    :mock      (mock/create)
    (throw (js/Error. (str "Unknown backend: " backend-kw
                            ". Expected :hypercore or :mock.")))))
