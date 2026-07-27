// Shared vocabulary for the zzStructure POC. No dependencies on any other
// module in this project — every other layer imports from here.

// ---------------------------------------------------------------------------
// Branded id types (cheap insurance against passing a CellId where a
// DimensionId is expected, etc. — these are erased at runtime, they only
// help the compiler).
// ---------------------------------------------------------------------------

export type UserId = string & { readonly __brand: "UserId" };
export type CellId = string & { readonly __brand: "CellId" };
export type DimensionId = string & { readonly __brand: "DimensionId" };

export const asUserId = (s: string): UserId => s as UserId;
export const asCellId = (s: string): CellId => s as CellId;
export const asDimensionId = (s: string): DimensionId => s as DimensionId;

// ---------------------------------------------------------------------------
// Cell — a discriminated union on `kind`, matching spec §4.1.
// ---------------------------------------------------------------------------

interface CellBase {
  id: CellId;
  ownerId: UserId;
}

export interface DocumentCell extends CellBase {
  kind: "document";
  documentId: string;
}

export interface DimensionCell extends CellBase {
  kind: "dimension";
  dimensionId: DimensionId;
}

export interface ViewCell extends CellBase {
  kind: "view";
  viewId: string;
}

export interface NamespaceHeadCell extends CellBase {
  kind: "namespaceHead";
  name: string;
}

export interface CloneCell extends CellBase {
  kind: "clone";
  of: CellId;
}

export interface PlainCell extends CellBase {
  kind: "plain";
}

export type Cell =
  | DocumentCell
  | DimensionCell
  | ViewCell
  | NamespaceHeadCell
  | CloneCell
  | PlainCell;

// ---------------------------------------------------------------------------
// Dimension — spec §4.2.
// ---------------------------------------------------------------------------

export interface Dimension {
  id: DimensionId;
  namespace: string;
  name: string;
  qualifiedName: string;
  dimensionCellId: CellId;
  ownerId: UserId;
}

// ---------------------------------------------------------------------------
// Connection — spec §4.3. Stored twice per edge (once on each cell), mirrored
// by link/unlink.
// ---------------------------------------------------------------------------

export interface Connection {
  cellId: CellId;
  dimensionId: DimensionId;
  negwardId: CellId | null;
  poswardId: CellId | null;
}

// ---------------------------------------------------------------------------
// Snapshot — the on-disk file format, spec §4.4.
// ---------------------------------------------------------------------------

export interface Snapshot {
  schemaVersion: 1;
  ownerId: UserId;
  revision: number;
  cells: Cell[];
  dimensions: Dimension[];
  connections: Connection[];
}

// ---------------------------------------------------------------------------
// Authorization file — spec §4.5.
// ---------------------------------------------------------------------------

export interface AuthorizedUser {
  id: UserId;
  displayName: string;
  handle: string;
  dataFile: string;
}

export interface AuthorizationFile {
  users: AuthorizedUser[];
}

// ---------------------------------------------------------------------------
// Engine error codes — spec §8. The HTTP layer maps each of these onto a
// status code in one place (routes/structures.ts).
// ---------------------------------------------------------------------------

export type EngineErrorCode =
  | "self_link_forbidden"
  | "validation_error"
  | "unknown_structure"
  | "unknown_cell"
  | "unknown_dimension"
  | "no_such_connection"
  | "foreign_cell_not_found"
  | "duplicate_dimension"
  | "restriction_r_violation"
  | "revision_conflict";

export interface EngineError {
  code: EngineErrorCode;
  message?: string;
}

export type Result<T> =
  | { ok: true; value: T }
  | { ok: false; error: EngineError };

export const ok = <T>(value: T): Result<T> => ({ ok: true, value });
export const err = <T = never>(
  code: EngineErrorCode,
  message?: string
): Result<T> => ({ ok: false, error: { code, message } });

// ---------------------------------------------------------------------------
// View rendering shapes — spec §7.1.
// ---------------------------------------------------------------------------

export interface PlacedCell {
  cellId: CellId;
  x: number;
  y: number;
  z: number;
  isVirtualCopy: boolean;
}

export interface ViewResult {
  revision: number;
  view: "h-view" | "i-view";
  axes: { x: DimensionId; y: DimensionId; z: DimensionId | null };
  accursed: CellId;
  placedCells: PlacedCell[];
  cells: Record<string, Cell>;
  dimensions: Record<string, Dimension>;
}

// Fixed system ids — literal by convention, identical across every install
// (spec §5, §9.1). Two dimensions collide with future extension only if the
// spec's own table changes.
export const SYSTEM_DIMENSION_IDS = {
  DIMENSIONS: asDimensionId("00000000-0000-7000-8000-00000000D001"),
  NAMESPACES: asDimensionId("00000000-0000-7000-8000-00000000D002"),
  NS_MEMBERS: asDimensionId("00000000-0000-7000-8000-00000000D003"),
  NS_SIBLINGS: asDimensionId("00000000-0000-7000-8000-00000000D004"),
  VIEWS: asDimensionId("00000000-0000-7000-8000-00000000D005"),
  CLONES: asDimensionId("00000000-0000-7000-8000-00000000D006"),
  USER_VIEWS: asDimensionId("00000000-0000-7000-8000-00000000D007"),
} as const;

export const SYSTEM_DIMENSION_CELL_IDS = {
  DIMENSIONS: asCellId("00000000-0000-7000-8000-00000000C001"),
  NAMESPACES: asCellId("00000000-0000-7000-8000-00000000C002"),
  NS_MEMBERS: asCellId("00000000-0000-7000-8000-00000000C003"),
  NS_SIBLINGS: asCellId("00000000-0000-7000-8000-00000000C004"),
  VIEWS: asCellId("00000000-0000-7000-8000-00000000C005"),
  CLONES: asCellId("00000000-0000-7000-8000-00000000C006"),
  USER_VIEWS: asCellId("00000000-0000-7000-8000-00000000C007"),
} as const;
