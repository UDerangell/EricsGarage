// The only module in this project that touches the filesystem. Matches the
// load/save port from spec §3.3 exactly. Swapping this file for a database
// adapter later means implementing the same two functions against a
// different backend.

import * as fs from "fs";
import * as path from "path";
import { Snapshot } from "./types";

/** Loads a Snapshot from disk, or null if the file doesn't exist. */
export function load(filePath: string): Snapshot | null {
  if (!fs.existsSync(filePath)) return null;
  const raw = fs.readFileSync(filePath, "utf-8");
  return JSON.parse(raw) as Snapshot;
}

/**
 * Writes a Snapshot to disk atomically: write to a temp file in the same
 * directory, then rename over the target. This avoids ever leaving a
 * half-written (and therefore corrupt) JSON file on disk if the process is
 * killed mid-write.
 */
export function save(filePath: string, snapshot: Snapshot): void {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
  const tmpPath = path.join(
    dir,
    `.${path.basename(filePath)}.${process.pid}.${Date.now()}.tmp`
  );
  fs.writeFileSync(tmpPath, JSON.stringify(snapshot, null, 2), "utf-8");
  fs.renameSync(tmpPath, filePath);
}
