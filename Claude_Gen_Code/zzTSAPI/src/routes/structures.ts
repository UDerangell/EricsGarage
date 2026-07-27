import { Router, Request, Response, NextFunction } from "express";
import { Auth } from "../auth";
import * as engine from "../engine";
import { Store } from "../store";
import {
  AuthorizedUser,
  CellId,
  DimensionId,
  EngineError,
  UserId,
  asCellId,
  asDimensionId,
  asUserId,
} from "../types";

// ---------------------------------------------------------------------------
// Error mapping — spec §8. Every route funnels engine/auth errors through
// this one place.
// ---------------------------------------------------------------------------

const STATUS_BY_CODE: Record<EngineError["code"], number> = {
  self_link_forbidden: 400,
  validation_error: 400,
  unknown_structure: 404,
  unknown_cell: 404,
  unknown_dimension: 404,
  no_such_connection: 404,
  foreign_cell_not_found: 404,
  duplicate_dimension: 409,
  restriction_r_violation: 409,
  revision_conflict: 409,
};

function sendEngineError(res: Response, error: EngineError): void {
  const status = STATUS_BY_CODE[error.code] ?? 400;
  const body: { error: string; message?: string } = { error: error.code };
  if (error.message) body.message = error.message;
  res.status(status).json(body);
}

function sendValidationError(res: Response, message: string): void {
  res.status(400).json({ error: "validation_error", message });
}

// ---------------------------------------------------------------------------
// Auth middleware — spec §6, applied to every /structures/:id route.
//
// Resolution order (must not be reordered — TC-27 depends on unknown
// structure being checked before any ownership check):
//   1. bearer missing/malformed/unknown -> 401 unauthorized
//   2. :id not in authorization.json    -> 404 unknown_structure
//   3. mutating (POST/DELETE) + caller !== :id -> 403 forbidden
//   4. reads: no further check
// ---------------------------------------------------------------------------

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Express {
    interface Request {
      caller?: AuthorizedUser;
      structureId?: UserId;
    }
  }
}

function authMiddleware(auth: Auth) {
  return (req: Request, res: Response, next: NextFunction) => {
    const caller = auth.resolveBearer(req.header("Authorization"));
    if (!caller) {
      res.status(401).json({ error: "unauthorized" });
      return;
    }
    const structureId = req.params.id!;
    if (!auth.isKnownStructure(structureId)) {
      res.status(404).json({ error: "unknown_structure" });
      return;
    }
    const isMutating = req.method === "POST" || req.method === "DELETE";
    if (isMutating && caller.id !== structureId) {
      res.status(403).json({ error: "forbidden" });
      return;
    }
    req.caller = caller;
    req.structureId = asUserId(structureId);
    next();
  };
}

// ---------------------------------------------------------------------------
// Small body-validation helpers (spec §8: validation_error on missing or
// malformed fields).
// ---------------------------------------------------------------------------

function requireString(
  body: unknown,
  field: string
): { ok: true; value: string } | { ok: false; message: string } {
  const v = (body as Record<string, unknown> | null)?.[field];
  if (typeof v !== "string" || v.length === 0) {
    return { ok: false, message: `"${field}" must be a non-empty string` };
  }
  return { ok: true, value: v };
}

function optionalBoolean(body: unknown, field: string): boolean | undefined {
  const v = (body as Record<string, unknown> | null)?.[field];
  return typeof v === "boolean" ? v : undefined;
}

function optionalNumber(body: unknown, field: string): number | undefined {
  const v = (body as Record<string, unknown> | null)?.[field];
  return typeof v === "number" ? v : undefined;
}

// ---------------------------------------------------------------------------
// Router factory
// ---------------------------------------------------------------------------

export function createStructuresRouter(store: Store, auth: Auth): Router {
  const router = Router();
  const guard = authMiddleware(auth);

  // 1. GET /structures/:id/view
  router.get("/structures/:id/view", guard, (req, res) => {
    const structureId = req.structureId!;
    const snapshot = store.getSnapshot(structureId)!;
    const { accursed, view, x, y, z } = req.query;
    if (typeof accursed !== "string" || typeof view !== "string" || typeof x !== "string" || typeof y !== "string") {
      return sendValidationError(res, "accursed, view, x, and y query params are required");
    }
    if (view !== "h-view" && view !== "i-view") {
      return sendValidationError(res, 'view must be "h-view" or "i-view"');
    }
    const result = engine.renderView(snapshot, {
      accursed: asCellId(accursed),
      view,
      x: asDimensionId(x),
      y: asDimensionId(y),
      z: typeof z === "string" ? asDimensionId(z) : null,
    });
    if (!result.ok) return sendEngineError(res, result.error);
    res.status(200).json(result.value);
  });

  // 2. GET /structures/:id/cells/:cellId
  router.get("/structures/:id/cells/:cellId", guard, (req, res) => {
    const snapshot = store.getSnapshot(req.structureId!)!;
    const cellId = asCellId(req.params.cellId!);
    const cell = engine.findCell(snapshot, cellId);
    if (!cell) return sendEngineError(res, { code: "unknown_cell" });
    const dimensionsPresent = engine.dimensionsPresent(snapshot, cellId);
    res.status(200).json({ cell, dimensionsPresent });
  });

  // 3. GET /structures/:id/dimensions
  router.get("/structures/:id/dimensions", guard, (req, res) => {
    const snapshot = store.getSnapshot(req.structureId!)!;
    res.status(200).json({ dimensions: snapshot.dimensions });
  });

  // 4. POST /structures/:id/links
  router.post("/structures/:id/links", guard, async (req, res) => {
    const a = requireString(req.body, "a");
    const b = requireString(req.body, "b");
    const dimension = requireString(req.body, "dimension");
    if (!a.ok) return sendValidationError(res, a.message);
    if (!b.ok) return sendValidationError(res, b.message);
    if (!dimension.ok) return sendValidationError(res, dimension.message);
    const splice = optionalBoolean(req.body, "splice");
    const allowSelfRing = optionalBoolean(req.body, "allowSelfRing");
    const expectedRevision = optionalNumber(req.body, "expectedRevision");

    const result = await store.withUserLock(
      req.structureId!,
      (snapshot) => {
        const r = engine.link(snapshot, asCellId(a.value), asCellId(b.value), asDimensionId(dimension.value), {
          splice,
          allowSelfRing,
        });
        if (!r.ok) return r;
        return { ok: true as const, value: { snapshot: r.value } };
      },
      { expectedRevision }
    );
    if (!result.ok) return sendEngineError(res, result.error);
    res.status(200).json({ revision: result.value.revision });
  });

  // 5. DELETE /structures/:id/links
  router.delete("/structures/:id/links", guard, async (req, res) => {
    const a = requireString(req.body, "a");
    const b = requireString(req.body, "b");
    const dimension = requireString(req.body, "dimension");
    if (!a.ok) return sendValidationError(res, a.message);
    if (!b.ok) return sendValidationError(res, b.message);
    if (!dimension.ok) return sendValidationError(res, dimension.message);

    const result = await store.withUserLock(req.structureId!, (snapshot) => {
      const r = engine.unlink(snapshot, asCellId(a.value), asCellId(b.value), asDimensionId(dimension.value));
      if (!r.ok) return r;
      return { ok: true as const, value: { snapshot: r.value } };
    });
    if (!result.ok) return sendEngineError(res, result.error);
    res.status(200).json({ revision: result.value.revision });
  });

  // 6. POST /structures/:id/dimensions
  router.post("/structures/:id/dimensions", guard, async (req, res) => {
    const name = requireString(req.body, "name");
    const namespace = requireString(req.body, "namespace");
    if (!name.ok) return sendValidationError(res, name.message);
    if (!namespace.ok) return sendValidationError(res, namespace.message);

    const result = await store.withUserLock(req.structureId!, (snapshot) =>
      engine.addDimension(snapshot, name.value, namespace.value)
    );
    if (!result.ok) return sendEngineError(res, result.error);
    res.status(200).json({ dimension: result.value.dimension, revision: result.value.revision });
  });

  // 7. POST /structures/:id/clones
  router.post("/structures/:id/clones", guard, async (req, res) => {
    const of = requireString(req.body, "of");
    if (!of.ok) return sendValidationError(res, of.message);

    const result = await store.withUserLock(req.structureId!, (snapshot) =>
      engine.makeClone(snapshot, asCellId(of.value))
    );
    if (!result.ok) return sendEngineError(res, result.error);
    res.status(200).json({ cloneCellId: result.value.cloneCellId, revision: result.value.revision });
  });

  // 8. POST /structures/:id/documents
  router.post("/structures/:id/documents", guard, async (req, res) => {
    const documentId = requireString(req.body, "documentId");
    if (!documentId.ok) return sendValidationError(res, documentId.message);

    const result = await store.withUserLock(req.structureId!, (snapshot) => {
      const r = engine.findOrCreateDocumentCell(snapshot, documentId.value);
      return { ok: true as const, value: r };
    });
    if (!result.ok) return sendEngineError(res, result.error);
    res.status(200).json({ cellId: result.value.cellId, created: result.value.created, revision: result.value.revision });
  });

  // 9. POST /structures/:id/foreign-cells
  router.post("/structures/:id/foreign-cells", guard, async (req, res) => {
    const foreignCellId = requireString(req.body, "foreignCellId");
    const ownerId = requireString(req.body, "ownerId");
    if (!foreignCellId.ok) return sendValidationError(res, foreignCellId.message);
    if (!ownerId.ok) return sendValidationError(res, ownerId.message);

    if (!auth.isKnownStructure(ownerId.value)) {
      return sendEngineError(res, { code: "unknown_structure" });
    }
    const foreignSnapshot = store.getSnapshot(asUserId(ownerId.value))!;

    const result = await store.withUserLock(req.structureId!, (snapshot) =>
      engine.importForeignCell(snapshot, foreignSnapshot, asCellId(foreignCellId.value))
    );
    if (!result.ok) return sendEngineError(res, result.error);
    res.status(200).json({ cell: result.value.cell, revision: result.value.revision });
  });

  // 10. GET /structures/:id/export
  router.get("/structures/:id/export", guard, (req, res) => {
    const snapshot = store.getSnapshot(req.structureId!)!;
    res.status(200).json(snapshot);
  });

  return router;
}
