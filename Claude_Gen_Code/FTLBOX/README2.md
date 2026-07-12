# FTLBOX

A terminal application for sharing and syncing folders peer-to-peer, with
no central server. Built directly on the modules that power the [Pear
runtime](https://pears.com/) (Holepunch's P2P stack):

| Module        | What it's used for here                                                   |
|---------------|-----------------------------------------------------------------------------|
| `corestore`   | Local on-disk storage for the append-only logs ("hypercores") a drive is built from. |
| `hyperdrive`  | A versioned, file-system-like structure (put/get/list/diff/mirror) stored as a hypercore. |
| `hyperswarm`  | Peer-to-peer networking: announces/looks up drives on the **DHT** (Distributed Hash Table) and opens encrypted connections to peers. |
| `localdrive`  | Wraps a normal folder so it can be mirrored to/from a hyperdrive with the same API. |

Every drive is identified by a 32-byte **public key**. Whoever has that key
can find and replicate the drive over the DHT - there is no server, no
account, no central index.

---

## 1. Installation

FTLBOX is a plain Node.js CLI (Node 18+ recommended) that uses the same
building blocks the Pear runtime is built on.

Both Alice and Bob run the same steps, each on their own machine:

```bash
# 1. Get the code (copy the ftlbox/ folder you were given, or clone your repo)
cd ftlbox

# 2. Install dependencies
npm install

# 3. (optional) Install it as a global command
npm link
# now you can just type `ftlbox ...` instead of `node bin/ftlbox.js ...`
```

If you'd rather run it through the actual **Pear** runtime instead of plain
Node (e.g. to eventually ship it as a `pear://` link others can run with
`pear run`), install Pear globally and run the same entry point through it:

```bash
npm install -g pear
pear run . create alice-drive     # runs bin/ftlbox.js inside the Pear runtime
```

Everything below assumes the plain-Node form, `node bin/ftlbox.js ...`
(or `ftlbox ...` after `npm link`). Run every command from inside the
`ftlbox/` project folder - FTLBOX keeps a small `ftlbox.json` registry file
and an `ftlbox-data/` storage folder there to remember your drives between
commands.

> Tip: if Alice and Bob are testing on the **same** machine, just check out
> two separate copies of the `ftlbox/` folder (e.g. `alice/` and `bob/`) so
> their registries and storage don't collide, and `cd` into the right one
> for each command below.

---

## 2. Command reference

```
ftlbox create <name>                       create a new writable hyperdrive
ftlbox add <name> <dir>                    add a local directory's contents to your drive
ftlbox addfile <name> <file> [drivePath]   add a single local file to your drive
ftlbox get <name> <drivePath> <outFile>    extract one file from a drive (yours or a pulled one)
ftlbox seed <name>                         announce your drive on the DHT and serve it (stays running)
ftlbox pull <key> <destDir> [--name n]     pull a drive by its public key into destDir
ftlbox diff <name>                         compare your pulled copy's version against the live one
ftlbox info <name>                         show a drive's public key / version
ftlbox list                                list all drives FTLBOX knows about
```

`<name>` is just a short local label you choose, e.g. `alice-drive`. FTLBOX
remembers, for each name, whether it's a drive you own or a copy you pulled,
its storage folder, and (for pulled copies) which real directory you last
pulled it into and which version you're at.

---

## 3. Walkthrough of every use case

### Alice creates and shares her drive

```bash
# Alice creates a new hyperdrive and gets a public key
ftlbox create alice-drive
#   Created drive "alice-drive"
#   Public key: 6e2f...<64 hex chars>...

# Alice adds the contents of a directory to her hyperdrive
ftlbox add alice-drive ./my-project

# Alice seeds her hyperdrive to the DHT (this announces it and keeps running -
# leave this terminal open; peers can only pull while this is running,
# unless you re-run `seed` later)
ftlbox seed alice-drive
#   Seeding "alice-drive"
#   public key : 6e2f...
#   Announced on the DHT. Leave this running so peers can connect. Ctrl+C to stop.

# Alice sends Bob her public key (outside the scope of this system - text
# it, email it, read it out loud, whatever)
```

### Bob creates and shares his drive, then pulls Alice's

```bash
# Bob creates a new hyperdrive and gets a public key
ftlbox create bob-drive

# Bob adds the contents of a directory to his hyperdrive
ftlbox add bob-drive ./bobs-stuff

# Bob seeds his hyperdrive to the DHT (leave running, in another terminal
# or another tab)
ftlbox seed bob-drive

# Bob sends Alice his public key (outside the scope of this system)

# Bob pulls the latest version of Alice's hyperdrive into an empty directory
# (run this in a separate terminal/tab from `seed`, since `seed` blocks)
ftlbox pull 6e2f...aliceskeyhex... ./alice-copy --name alice-copy
#   Pulled "alice-copy" (version 1) into /.../alice-copy (N file(s) written/updated)
```

`--name alice-copy` is just the local label Bob wants to use for his copy of
Alice's drive in future commands (`diff`, re-`pull`, `get`, etc).

### Alice updates her drive; Bob notices and re-pulls

```bash
# Alice adds a file to her hyperdrive - this creates a new version
ftlbox addfile alice-drive ./notes/plan.md /plan.md
#   Added "./notes/plan.md" to "alice-drive" as "/plan.md" -> new version 2

# (Alice's `seed` process needs to be running for Bob to see this - if she
# stopped it to run `addfile`, she should `ftlbox seed alice-drive` again)

# Bob compares his pulled copy's version against the live version on the network
ftlbox diff alice-copy
#   "alice-copy": local copy is version 1, latest on the network is version 2.
#   Changed paths:
#     added    /plan.md

# Bob pulls the latest version into the SAME directory he used before
ftlbox pull 6e2f...aliceskeyhex... ./alice-copy --name alice-copy
#   Pulled "alice-copy" (version 2) into /.../alice-copy (1 file(s) written/updated)
```

Re-running `pull` with the same `--name` (or just letting it default) reuses
the same local replica and destination folder that was recorded the first
time, and only writes the files that actually changed.

### Bob edits a file from Alice's drive and sends it back

```bash
# Bob copies a file from Alice's hyperdrive to his own hyperdrive
#   (a) pull it out to a normal file:
ftlbox get alice-copy /plan.md ./plan-with-comments.md
#   (b) edit it (outside the scope of this system - open it in any editor)
#       ...Bob adds his comments to plan-with-comments.md...
#   (c) add the edited file into Bob's own drive:
ftlbox addfile bob-drive ./plan-with-comments.md /plan-with-comments.md

# Bob's `seed bob-drive` process (already running) will now serve this new
# version automatically.

# Alice pulls the latest version of Bob's hyperdrive and retrieves the file
ftlbox pull <bobs-key-hex> ./bob-copy --name bob-copy
ftlbox get bob-copy /plan-with-comments.md ./plan-with-comments.md
```

---

## 4. How the pieces map to Pear/Hyperdrive concepts

- **Public key** = the identity of a hyperdrive. Anyone with it can find and
  replicate the drive; it's the only thing you need to "send" to a peer.
- **`seed`** = `swarm.join(drive.discoveryKey, { server: true, client: true })`.
  This announces the drive's discovery key on the DHT and keeps the process
  running so it can accept replication connections from anyone looking that
  key up. This is why it has to stay running for others to pull from you.
- **`pull`** = open a replica of the drive by its public key, join the DHT
  as a client to find the seeder, call `drive.update()` to fetch the latest
  state, then mirror the hyperdrive's contents onto your local filesystem
  with `drive.mirror(new Localdrive(destDir))`.
- **Versioning** = every `add`/`addfile` is a write into the drive's
  underlying hypercore, which bumps `drive.version` - conceptually similar
  to a git commit. `diff(oldVersion, '/')` lists exactly what changed
  between that version and the live one.
- Every file in `lib/drive.js` has inline comments next to each operation
  explaining exactly which Pear/Hyperdrive/Hyperswarm call is doing the work.

---

## 5. Project layout

```
ftlbox/
  bin/ftlbox.js     CLI entry point (argument parsing + dispatch only)
  lib/drive.js       all Pear/Hyperdrive/Hyperswarm logic, heavily commented
  lib/registry.js    local bookkeeping (ftlbox.json) mapping names -> keys/paths
  test/full-flow.js  automated end-to-end test of every use case above
  package.json
```

Run `npm test` to exercise the full Alice/Bob workflow automatically. (The
test replicates over an in-memory stream instead of a real network so it can
run in restricted/offline CI environments; in normal use, `seed`/`pull`/`diff`
talk to the real DHT via Hyperswarm exactly as described above.)
