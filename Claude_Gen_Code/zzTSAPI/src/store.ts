// Owns the process model from spec §3.4: one Node process holding both
// structures in memory, loaded/bootstrapped eagerly at startup, with a
// per-user mutex serializing mutating requests. This is where `revision`
// bookkeeping actually happens — engine.ts never touches it.

import * as path from "path";
import { Auth } from "./auth";
import * as engine from "./engine";
import * as persistence from "./persistence";
import { EngineError, Result, Snapshot, UserId } from "./types";

interface UserSlot {
  snapshot: Snapshot;
  filePath: string;
  /** Tail of the per-user promise chain; each mutation appends to this. */
  lockTail: Promise<unknown>;
}

export class Store {
  private slots = new Map<UserId, UserSlot>();

  private constructor(private readonly auth: Auth, private readonly dataDir: string) {}

  /**
   * Eager bootstrap at startup: for every user in authorization.json, load
   * their file if it exists, or bootstrap + save a fresh one if it doesn't.
   * This is intentionally eager (rather than lazy-on-first-request) so file
   * contents are inspectable immediately after the server starts, matching
   * the assumption in spec §9's test plan.
   */
  static initialize(auth: Auth, dataDir: string): Store {
    const store = new Store(auth, dataDir);
    for (const user of auth.users) {
      const filePath = path.join(dataDir, user.dataFile);
      let snapshot = persistence.load(filePath);
      if (snapshot === null) {
        snapshot = engine.bootstrap(user.id);
        persistence.save(filePath, snapshot);
      } else {
        snapshot = engine.verifyAndRepairMirrors(snapshot);
      }
      store.slots.set(user.id, { snapshot, filePath, lockTail: Promise.resolve() });
    }
    return store;
  }

  /** Read-only access — no lock required (spec §6.4: reads are unrestricted). */
  getSnapshot(userId: UserId): Snapshot | undefined {
    return this.slots.get(userId)?.snapshot;
  }

  /**
   * Runs `fn` against the current snapshot for `userId` under that user's
   * mutex. On success, persists the returned snapshot with `revision`
   * incremented by exactly 1 and updates the in-memory copy; on failure,
   * nothing is written and the in-memory snapshot is untouched.
   *
   * The "mutex" here is a promise chain: on Node's single-threaded event
   * loop this exists to stop two mutating requests for the *same* user from
   * interleaving across `await` points, not to provide true parallelism —
   * two different users can run concurrently with no coordination at all.
   */
  async withUserLock<T>(
    userId: UserId,
    fn: (snapshot: Snapshot) => Result<{ snapshot: Snapshot } & T>,
    options: { expectedRevision?: number } = {}
  ): Promise<Result<{ revision: number } & T>> {
    const slot = this.slots.get(userId);
    if (!slot) {
      return { ok: false, error: { code: "unknown_structure" } as EngineError };
    }

    const run = async (): Promise<Result<{ revision: number } & T>> => {
      if (
        options.expectedRevision !== undefined &&
        options.expectedRevision !== slot.snapshot.revision
      ) {
        return { ok: false, error: { code: "revision_conflict" } };
      }
      const result = fn(slot.snapshot);
      if (!result.ok) return result;
      const { snapshot: newSnapshotRaw, ...rest } = result.value;
      if (
        !newSnapshotRaw ||
        !Array.isArray(newSnapshotRaw.cells) ||
        !Array.isArray(newSnapshotRaw.dimensions) ||
        !Array.isArray(newSnapshotRaw.connections)
      ) {
        throw new Error(
          "withUserLock: engine function returned a malformed snapshot (missing cells/dimensions/connections) — refusing to persist"
        );
      }
      const newSnapshot: Snapshot = { ...newSnapshotRaw, revision: slot.snapshot.revision + 1 };
      persistence.save(slot.filePath, newSnapshot);
      slot.snapshot = newSnapshot;
      return { ok: true, value: { revision: newSnapshot.revision, ...(rest as T) } };
    };

    // Chain onto the tail so this call only runs after the previous one for
    // this user has fully settled, regardless of whether it succeeded.
    const resultPromise = slot.lockTail.then(run, run);
    slot.lockTail = resultPromise.catch(() => undefined);
    return resultPromise;
  }
}
