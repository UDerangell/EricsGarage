// Loads authorization.json once at startup and resolves bearer tokens
// against it. Deciding 403 (caller !== target structure) and 404 (unknown
// structure id in the path) is the HTTP layer's job, since those checks
// depend on route parameters this module never sees — see spec §6.

import * as fs from "fs";
import { AuthorizationFile, AuthorizedUser, UserId, asUserId } from "./types";

export class Auth {
  private byId = new Map<UserId, AuthorizedUser>();

  private constructor(private readonly file: AuthorizationFile) {
    for (const u of file.users) {
      this.byId.set(u.id, u);
    }
  }

  static loadFromFile(path: string): Auth {
    const raw = fs.readFileSync(path, "utf-8");
    const parsed = JSON.parse(raw) as AuthorizationFile;
    return new Auth(parsed);
  }

  get users(): AuthorizedUser[] {
    return this.file.users;
  }

  isKnownStructure(id: string): boolean {
    return this.byId.has(asUserId(id));
  }

  getUser(id: string): AuthorizedUser | undefined {
    return this.byId.get(asUserId(id));
  }

  /**
   * Resolves an `Authorization: Bearer <uuid>` header. Returns null if the
   * header is missing, malformed, or the uuid isn't a known user — spec §6
   * step 1, always a 401 regardless of what's being requested.
   */
  resolveBearer(header: string | undefined): AuthorizedUser | null {
    if (!header) return null;
    const match = /^Bearer\s+(.+)$/i.exec(header.trim());
    if (!match) return null;
    const token = match[1]!.trim();
    return this.byId.get(asUserId(token)) ?? null;
  }
}
