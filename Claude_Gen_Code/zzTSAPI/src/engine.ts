// Pure domain engine — a port of the ZZStructure logic described in spec
// §3.2. Every exported function here takes a Snapshot and returns either a
// new Snapshot (never mutates its input) or an EngineError. Nothing in this
// file touches `fs`, `http`, or the `revision` counter — that bookkeeping is
// owned by store.ts.

import { v7 as uuidv7 } from "uuid";
import {
  Cell,
  CellId,
  Connection,
  Dimension,
  DimensionId,
  DocumentCell,
  Result,
  Snapshot,
  UserId,
  ViewResult,
  asCellId,
  asDimensionId,
  err,
  ok,
  SYSTEM_DIMENSION_CELL_IDS as SC,
  SYSTEM_DIMENSION_IDS as SD,
} from "./types";

// ---------------------------------------------------------------------------
// Small internal helpers
// ---------------------------------------------------------------------------

const newCellId = (): CellId => asCellId(uuidv7());
const newDimensionId = (): DimensionId => asDimensionId(uuidv7());

const cloneSnapshot = (s: Snapshot): Snapshot => ({
  ...s,
  cells: s.cells.map((c) => ({ ...c })),
  dimensions: s.dimensions.map((d) => ({ ...d })),
  connections: s.connections.map((c) => ({ ...c })),
});

export function findCell(s: Snapshot, id: CellId): Cell | undefined {
  return s.cells.find((c) => c.id === id);
}

export function findDimensionById(
  s: Snapshot,
  id: DimensionId
): Dimension | undefined {
  return s.dimensions.find((d) => d.id === id);
}

export function findDimensionByQualifiedName(
  s: Snapshot,
  qualifiedName: string
): Dimension | undefined {
  return s.dimensions.find((d) => d.qualifiedName === qualifiedName);
}

function getConn(
  s: Snapshot,
  cellId: CellId,
  dimensionId: DimensionId
): Connection | undefined {
  return s.connections.find(
    (c) => c.cellId === cellId && c.dimensionId === dimensionId
  );
}

// Returns the (possibly newly created, already-pushed) connection record for
// cellId/dimensionId, mutating `s.connections` in place. Caller must only
// call this on a snapshot obtained from cloneSnapshot.
function ensureConn(
  s: Snapshot,
  cellId: CellId,
  dimensionId: DimensionId
): Connection {
  let rec = getConn(s, cellId, dimensionId);
  if (!rec) {
    rec = { cellId, dimensionId, negwardId: null, poswardId: null };
    s.connections.push(rec);
  }
  return rec;
}

/** All dimensions on which `cellId` has at least one connection record. */
export function dimensionsPresent(s: Snapshot, cellId: CellId): Dimension[] {
  const dimIds = new Set(
    s.connections.filter((c) => c.cellId === cellId).map((c) => c.dimensionId)
  );
  return s.dimensions.filter((d) => dimIds.has(d.id));
}

// ---------------------------------------------------------------------------
// link / unlink — spec §7.4 / §7.5, Restriction R.
// ---------------------------------------------------------------------------

export interface LinkOptions {
  splice?: boolean;
  allowSelfRing?: boolean;
}

/**
 * Links `a` posward-to `b` along `dimensionId`, mirrored on both cells.
 *
 * Restriction R: a cell may have at most one posward and one negward
 * neighbor per dimension. Linking into an already-occupied slot is rejected
 * unless `splice` is set, in which case the existing occupant is pushed
 * further along the chain (b is spliced in between a and a's old posward
 * neighbor).
 */
export function link(
  snapshot: Snapshot,
  a: CellId,
  b: CellId,
  dimensionId: DimensionId,
  options: LinkOptions = {}
): Result<Snapshot> {
  if (a === b && !options.allowSelfRing) {
    return err("self_link_forbidden", "a and b are the same cell");
  }
  if (!findCell(snapshot, a)) return err("unknown_cell", `${a} not found`);
  if (!findCell(snapshot, b)) return err("unknown_cell", `${b} not found`);
  if (!findDimensionById(snapshot, dimensionId)) {
    return err("unknown_dimension", `${dimensionId} not found`);
  }

  const s = cloneSnapshot(snapshot);
  const connA = ensureConn(s, a, dimensionId);
  const connB = ensureConn(s, b, dimensionId);

  const aOccupied = connA.poswardId !== null && connA.poswardId !== b;
  const bOccupied = connB.negwardId !== null && connB.negwardId !== a;

  if ((aOccupied || bOccupied) && !options.splice) {
    return err(
      "restriction_r_violation",
      "posward of the first cell is already occupied"
    );
  }

  const oldNext = connA.poswardId; // may be null, or the cell being spliced past
  const oldNextIsDifferent = oldNext !== null && oldNext !== b;

  connA.poswardId = b;
  connB.negwardId = a;

  if (options.splice && oldNextIsDifferent && oldNext !== null) {
    // Rewire: a -> b -> oldNext (oldNext's negward becomes b).
    const oldNextConn = ensureConn(s, oldNext, dimensionId);
    oldNextConn.negwardId = b;
    connB.poswardId = oldNext;
  }

  return ok(s);
}

/** Removes the a->b edge along `dimensionId`, mirrored on both cells. */
export function unlink(
  snapshot: Snapshot,
  a: CellId,
  b: CellId,
  dimensionId: DimensionId
): Result<Snapshot> {
  const connA = getConn(snapshot, a, dimensionId);
  const connB = getConn(snapshot, b, dimensionId);
  if (!connA || connA.poswardId !== b || !connB || connB.negwardId !== a) {
    return err("no_such_connection", `${a} -> ${b} not linked along ${dimensionId}`);
  }
  const s = cloneSnapshot(snapshot);
  const cA = ensureConn(s, a, dimensionId);
  const cB = ensureConn(s, b, dimensionId);
  cA.poswardId = null;
  cB.negwardId = null;
  return ok(s);
}

// ---------------------------------------------------------------------------
// addDimension — spec §7.6. Inserts the new dimension cell into the
// d.dimensions ring, and files it under its namespace head (creating the
// head + its d.namespace-members entry the first time that namespace is
// used in this structure).
// ---------------------------------------------------------------------------

export function addDimension(
  snapshot: Snapshot,
  name: string,
  namespace: string
): Result<{ snapshot: Snapshot; dimension: Dimension }> {
  const qualifiedName = `${namespace}.${name}`;
  if (findDimensionByQualifiedName(snapshot, qualifiedName)) {
    return err("duplicate_dimension", `${qualifiedName} already exists`);
  }

  let s = cloneSnapshot(snapshot);
  const dimensionCellId = newCellId();
  const dimensionId = newDimensionId();

  const dimensionCell: Cell = {
    id: dimensionCellId,
    kind: "dimension",
    dimensionId,
    ownerId: s.ownerId,
  };
  const dimension: Dimension = {
    id: dimensionId,
    namespace,
    name,
    qualifiedName,
    dimensionCellId,
    ownerId: s.ownerId,
  };
  s.cells.push(dimensionCell);
  s.dimensions.push(dimension);

  // Insert into the d.dimensions ring, just before it closes back on the
  // anchor cell (the ring's own dimension-cell).
  const anchor = SC.DIMENSIONS;
  const anchorConn = ensureConn(s, anchor, SD.DIMENSIONS);
  let lastCell = anchor;
  if (anchorConn.negwardId !== null) {
    lastCell = anchorConn.negwardId;
  } else {
    // Ring not closed yet (shouldn't happen post-bootstrap) — walk forward.
    let cursor = anchor;
    const seen = new Set<CellId>();
    while (true) {
      const c = getConn(s, cursor, SD.DIMENSIONS);
      if (!c || c.poswardId === null || seen.has(cursor)) break;
      seen.add(cursor);
      cursor = c.poswardId;
    }
    lastCell = cursor;
  }
  const spliceResult = link(s, lastCell, dimensionCellId, SD.DIMENSIONS, {
    splice: true,
  });
  if (!spliceResult.ok) return spliceResult as unknown as Result<never>;
  s = spliceResult.value;
  // Close the ring back to the anchor.
  const closeResult = link(s, dimensionCellId, anchor, SD.DIMENSIONS, {
    splice: true,
    allowSelfRing: dimensionCellId === anchor,
  });
  if (!closeResult.ok) return closeResult as unknown as Result<never>;
  s = closeResult.value;

  // File under the namespace head, creating the head on first use.
  let head = s.cells.find(
    (c): c is Cell & { kind: "namespaceHead" } =>
      c.kind === "namespaceHead" && (c as any).name === namespace
  );
  if (!head) {
    const headId = newCellId();
    head = { id: headId, kind: "namespaceHead", name: namespace, ownerId: s.ownerId };
    s.cells.push(head);
    const memberLink = link(s, head.id, dimensionCellId, SD.NS_MEMBERS, {
      splice: true,
    });
    if (!memberLink.ok) return memberLink as unknown as Result<never>;
    s = memberLink.value;
  } else {
    // Find the existing head's member, then walk the sibling chain to the end.
    const memberConn = getConn(s, head.id, SD.NS_MEMBERS);
    let lastSibling = memberConn?.poswardId ?? null;
    if (lastSibling === null) {
      // Defensive fallback: head exists but has no member yet.
      const memberLink = link(s, head.id, dimensionCellId, SD.NS_MEMBERS, {
        splice: true,
      });
      if (!memberLink.ok) return memberLink as unknown as Result<never>;
      s = memberLink.value;
      lastSibling = dimensionCellId;
    } else {
      const seen = new Set<CellId>();
      while (true) {
        const c = getConn(s, lastSibling, SD.NS_SIBLINGS);
        if (!c || c.poswardId === null || seen.has(lastSibling)) break;
        seen.add(lastSibling);
        lastSibling = c.poswardId;
      }
      const siblingLink = link(s, lastSibling, dimensionCellId, SD.NS_SIBLINGS, {
        splice: true,
      });
      if (!siblingLink.ok) return siblingLink as unknown as Result<never>;
      s = siblingLink.value;
    }
  }

  return ok({ snapshot: s, dimension });
}

// ---------------------------------------------------------------------------
// makeClone — spec §7.7. Chains multiple clones of the same cell off the
// original via D.CLONES.
// ---------------------------------------------------------------------------

export function makeClone(
  snapshot: Snapshot,
  of: CellId
): Result<{ snapshot: Snapshot; cloneCellId: CellId }> {
  if (!findCell(snapshot, of)) return err("unknown_cell", `${of} not found`);
  const s = cloneSnapshot(snapshot);
  const cloneCellId = newCellId();
  const cloneCell: Cell = { id: cloneCellId, kind: "clone", of, ownerId: s.ownerId };
  s.cells.push(cloneCell);
  const linked = link(s, of, cloneCellId, SD.CLONES, { splice: true });
  if (!linked.ok) return linked as unknown as Result<never>;
  return ok({ snapshot: linked.value, cloneCellId });
}

// ---------------------------------------------------------------------------
// findOrCreateDocumentCell — spec §7.8.
// ---------------------------------------------------------------------------

export function findOrCreateDocumentCell(
  snapshot: Snapshot,
  documentId: string
): { snapshot: Snapshot; cellId: CellId; created: boolean } {
  const existing = snapshot.cells.find(
    (c): c is DocumentCell => c.kind === "document" && c.documentId === documentId
  );
  if (existing) {
    return { snapshot, cellId: existing.id, created: false };
  }
  const s = cloneSnapshot(snapshot);
  const cellId = newCellId();
  const cell: DocumentCell = {
    id: cellId,
    kind: "document",
    documentId,
    ownerId: s.ownerId,
  };
  s.cells.push(cell);
  return { snapshot: s, cellId, created: true };
}

// ---------------------------------------------------------------------------
// importForeignCell — spec §7.9. Copies a cell's `kind` fields from the
// foreign owner's own snapshot into the caller's snapshot verbatim,
// preserving the true ownerId, without mutating the foreign snapshot.
// ---------------------------------------------------------------------------

export function importForeignCell(
  callerSnapshot: Snapshot,
  foreignSnapshot: Snapshot,
  foreignCellId: CellId
): Result<{ snapshot: Snapshot; cell: Cell }> {
  const foreignCell = findCell(foreignSnapshot, foreignCellId);
  if (!foreignCell) {
    return err("foreign_cell_not_found", `${foreignCellId} not found`);
  }
  const already = findCell(callerSnapshot, foreignCellId);
  if (already) {
    return ok({ snapshot: callerSnapshot, cell: already });
  }
  const s = cloneSnapshot(callerSnapshot);
  const importedCell: Cell = { ...foreignCell };
  s.cells.push(importedCell);
  return ok({ snapshot: s, cell: importedCell });
}

// ---------------------------------------------------------------------------
// bootstrap — spec §5.
// ---------------------------------------------------------------------------

const SYSTEM_DIMENSIONS: Array<{
  key: keyof typeof SD;
  name: string;
}> = [
  { key: "DIMENSIONS", name: "dimensions" },
  { key: "NAMESPACES", name: "namespaces" },
  { key: "NS_MEMBERS", name: "namespace-members" },
  { key: "NS_SIBLINGS", name: "namespace-siblings" },
  { key: "VIEWS", name: "views" },
  { key: "CLONES", name: "clones" },
  { key: "USER_VIEWS", name: "user-views" },
];

export function freshSnapshot(ownerId: UserId): Snapshot {
  return { schemaVersion: 1, ownerId, revision: 0, cells: [], dimensions: [], connections: [] };
}

export function bootstrap(ownerId: UserId): Snapshot {
  let s = freshSnapshot(ownerId);

  // 1. Register the seven system dimensions and their cells (fixed ids).
  for (const { key, name } of SYSTEM_DIMENSIONS) {
    const dimensionId = SD[key];
    const cellId = SC[key];
    s.cells.push({ id: cellId, kind: "dimension", dimensionId, ownerId });
    s.dimensions.push({
      id: dimensionId,
      namespace: "d",
      name,
      qualifiedName: `d.${name}`,
      dimensionCellId: cellId,
      ownerId,
    });
  }

  // 2. Thread d.dimensions into a self-including ring containing all seven.
  const ring = [SC.DIMENSIONS, SC.NAMESPACES, SC.NS_MEMBERS, SC.NS_SIBLINGS, SC.VIEWS, SC.CLONES, SC.USER_VIEWS];
  for (let i = 0; i < ring.length; i++) {
    const from = ring[i]!;
    const to = ring[(i + 1) % ring.length]!;
    const res = link(s, from, to, SD.DIMENSIONS, { splice: true, allowSelfRing: from === to });
    if (!res.ok) throw new Error(`bootstrap ring link failed: ${res.error.code}`);
    s = res.value;
  }

  // 3. File all seven system dimensions under a `d`-namespace head cell.
  const dHeadId = newCellId();
  s.cells.push({ id: dHeadId, kind: "namespaceHead", name: "d", ownerId });
  {
    const res = link(s, dHeadId, ring[0]!, SD.NS_MEMBERS, { splice: true });
    if (!res.ok) throw new Error(`bootstrap ns-members link failed: ${res.error.code}`);
    s = res.value;
  }
  for (let i = 0; i < ring.length - 1; i++) {
    const res = link(s, ring[i]!, ring[i + 1]!, SD.NS_SIBLINGS, { splice: true });
    if (!res.ok) throw new Error(`bootstrap ns-siblings link failed: ${res.error.code}`);
    s = res.value;
  }

  // 4. Register HView and IView on d.views, and clone each onto d.user-views.
  const hViewId = newCellId();
  const iViewId = newCellId();
  s.cells.push({ id: hViewId, kind: "view", viewId: "h-view", ownerId });
  s.cells.push({ id: iViewId, kind: "view", viewId: "i-view", ownerId });
  {
    const res = link(s, hViewId, iViewId, SD.VIEWS, { splice: true });
    if (!res.ok) throw new Error(`bootstrap views link failed: ${res.error.code}`);
    s = res.value;
  }

  const hClone = makeClone(s, hViewId);
  if (!hClone.ok) throw new Error(`bootstrap h-view clone failed: ${hClone.error.code}`);
  s = hClone.value.snapshot;
  const iClone = makeClone(s, iViewId);
  if (!iClone.ok) throw new Error(`bootstrap i-view clone failed: ${iClone.error.code}`);
  s = iClone.value.snapshot;

  {
    const res = link(s, hClone.value.cloneCellId, iClone.value.cloneCellId, SD.USER_VIEWS, {
      splice: true,
    });
    if (!res.ok) throw new Error(`bootstrap user-views link failed: ${res.error.code}`);
    s = res.value;
  }

  return s;
}

/**
 * Verifies every connection record has a correctly mirrored counterpart and
 * repairs any that don't. Used when loading a possibly hand-edited file
 * (spec §5).
 */
export function verifyAndRepairMirrors(snapshot: Snapshot): Snapshot {
  const s = cloneSnapshot(snapshot);
  for (const conn of s.connections) {
    if (conn.poswardId !== null) {
      const mirror = ensureConn(s, conn.poswardId, conn.dimensionId);
      mirror.negwardId = conn.cellId;
    }
    if (conn.negwardId !== null) {
      const mirror = ensureConn(s, conn.negwardId, conn.dimensionId);
      mirror.poswardId = conn.cellId;
    }
  }
  return s;
}

// ---------------------------------------------------------------------------
// renderView — spec §7.1. A simplified grid-layout BFS over the x/y(/z)
// axis dimensions, starting from the "accursed" cell at the origin.
// ---------------------------------------------------------------------------

export function renderView(
  snapshot: Snapshot,
  params: {
    accursed: CellId;
    view: "h-view" | "i-view";
    x: DimensionId;
    y: DimensionId;
    z?: DimensionId | null;
  }
): Result<ViewResult> {
  const accursedCell = findCell(snapshot, params.accursed);
  if (!accursedCell) return err("unknown_cell", `${params.accursed} not found`);
  if (!findDimensionById(snapshot, params.x)) {
    return err("unknown_dimension", `${params.x} not found`);
  }
  if (!findDimensionById(snapshot, params.y)) {
    return err("unknown_dimension", `${params.y} not found`);
  }
  if (params.z && !findDimensionById(snapshot, params.z)) {
    return err("unknown_dimension", `${params.z} not found`);
  }

  type Coord = { x: number; y: number; z: number };
  const positions = new Map<CellId, Coord>();
  const placedCells: ViewResult["placedCells"] = [];
  const cellsOut: Record<string, Cell> = {};
  const queue: CellId[] = [params.accursed];
  positions.set(params.accursed, { x: 0, y: 0, z: 0 });

  const axes: Array<{ dim: DimensionId; axis: "x" | "y" | "z" }> = [
    { dim: params.x, axis: "x" },
    { dim: params.y, axis: "y" },
  ];
  if (params.z) axes.push({ dim: params.z, axis: "z" });

  while (queue.length > 0) {
    const currentId = queue.shift()!;
    const pos = positions.get(currentId)!;
    const cell = findCell(snapshot, currentId);
    if (!cell) continue;
    cellsOut[currentId] = cell;
    placedCells.push({ cellId: currentId, x: pos.x, y: pos.y, z: pos.z, isVirtualCopy: false });

    for (const { dim, axis } of axes) {
      const conn = getConn(snapshot, currentId, dim);
      if (!conn) continue;
      const neighbors: Array<[CellId | null, 1 | -1]> = [
        [conn.poswardId, 1],
        [conn.negwardId, -1],
      ];
      for (const [neighborId, delta] of neighbors) {
        if (!neighborId) continue;
        const nextPos: Coord = { ...pos, [axis]: pos[axis] + delta } as Coord;
        if (!positions.has(neighborId)) {
          positions.set(neighborId, nextPos);
          queue.push(neighborId);
        }
        // If already visited at a different coordinate, we simply leave the
        // first placement in place (a full virtual-copy model is out of
        // scope for this POC).
      }
    }
  }

  const dimensionsOut: Record<string, Dimension> = {};
  for (const { dim } of axes) {
    const d = findDimensionById(snapshot, dim);
    if (d) dimensionsOut[dim] = d;
  }

  return ok({
    revision: snapshot.revision,
    view: params.view,
    axes: { x: params.x, y: params.y, z: params.z ?? null },
    accursed: params.accursed,
    placedCells,
    cells: cellsOut,
    dimensions: dimensionsOut,
  });
}
