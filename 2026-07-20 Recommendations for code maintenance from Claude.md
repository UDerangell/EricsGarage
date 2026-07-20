- Chat session: https://claude.ai/share/e0ec794b-3e0c-4832-b32b-014373de81dd
- Prompt: Thank you very much for your hard work!  This application may be useful for a small community.  What recommendations do you have if I want to do future maintenance of this application in Claude Code?

Let me check current documentation on Claude Code project-context conventions before recommending specifics, since that's exactly the kind of product detail I should verify rather than assume.Glad it's useful — a few concrete recommendations, based specifically on what we ran into building this.

## 1. Put it in git before anything else

There's no version control yet — everything's been flat files in a folder. That's the single highest-leverage thing to fix first: Claude Code works far better (and far more safely) with a real repo, since it can diff its own changes, and you can review/revert anything before trusting it. `git init`, commit what you have now as a clean v0.02 baseline, then treat every future change as its own commit.

## 2. Add a `CLAUDE.md` at the project root

Claude Code automatically reads a `CLAUDE.md` file in the repo root at the start of every session — it's the right place to put the things that would otherwise need re-explaining each time. For this project specifically, I'd seed it with the gotchas we actually hit while building it, since these are exactly the kind of thing a future session would otherwise rediscover the hard way:

- **Corestore single-lock constraint**: a drive's storage folder can only be held open by one process at a time. This bit us directly (the "File descriptor could not be locked" bug) and will bite again if a future change opens the same drive twice concurrently.
- **`drive.version` starts at 1, not 0** — confirmed against the installed library, not assumed.
- **`drive.diff()`'s `{left, right}` shape**: `left` = current/live entry, `right` = entry at the old version. We had this backwards once already.
- **The sandbox/CI note**: real Hyperswarm/DHT connections can't be tested in a network-restricted environment (this one blocks local/loopback traffic) — `test/full-flow.js` substitutes an in-memory stream for the network join specifically because of this, via the `openAndSync`/`module.exports.joinSwarm` seam. Worth flagging so a future session doesn't "fix" the test by trying to make it hit the real DHT.
- **Registry side-effect rule**: version-pinned pulls must never update `lastVersion`/`pullDir` — that was a deliberate design decision, not an oversight, and it'd be easy to "simplify" it away by accident.
- Pointer to `README.md` for the command reference and design notes, so `CLAUDE.md` itself can stay short rather than duplicating it.

## 3. Keep `npm test` as the guardrail, and grow it deliberately

The test suite calls the real library functions, not a mock — that's what caught the two actual bugs we found (the lock issue and the diff semantics) rather than a superficial happy-path check. Make "run `npm test` before and after any change" a standing instruction in `CLAUDE.md`. When adding a new command, ask for a corresponding test addition in the same request, not as a follow-up — it's much cheaper to get that habit established now than to retrofit coverage later.

One real gap worth knowing about: the test suite can't verify actual DHT behavior, only the replication/versioning logic downstream of a connection. Periodically — especially after any change touching `joinSwarm`, `seed`, or `pull` — it's worth doing one real manual test between two actual machines (or two terminals on one machine with real networking) to catch anything the in-memory-stream substitution wouldn't.

## 4. Keep the "analyze before implementing" habit going

The back-and-forth we did — impact analysis first, decisions made explicit, then code — held up well and caught real design issues before they became bugs (the registry-side-effect question, the destination-directory strictness question, the register overwrite semantics). That's worth carrying into Claude Code sessions deliberately: ask it to talk through impact and open decisions on anything nontrivial before it starts editing, rather than letting it jump straight to a diff. It's easy to lose that discipline once a tool can just go implement something immediately.

## 5. A ready-made backlog

Everything discussed but not built is a natural set of scoped follow-up prompts, each already sized:

- `checkout` command (new directory, must be empty, validated version)
- Negative-offset version syntax, or the `versions`-then-`pull` discovery flow as an alternative
- Per-file/folder version history with real hyphen-compressed sparsity
- The pinning-server mode (watch list, multi-drive seeding, disk monitoring)
- macOS wrapping (persistent-daemon architecture, not per-command spawning) and/or the web-service wrapping (multi-tenant, key-custody questions)

Feeding these in one at a time, with the impact analysis first, is a good way to keep the codebase from accumulating undigested complexity.

## 6. Keep verifying against the actual installed source

Several of the accurate details in this conversation (the `diff` entry shape, the version-1 baseline, hyperdrive's actual API surface) came from reading `node_modules` and the library's own README directly rather than relying on general knowledge of the Holepunch stack, since it's a fast-moving ecosystem and API details drift across versions. That's a cheap, high-value habit to keep instructing Claude Code to do — checking the installed version's actual behavior before making changes that depend on its semantics — rather than assuming based on general familiarity with hyperdrive/hyperswarm.
