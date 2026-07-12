'use strict'
// ---------------------------------------------------------------------------
// This module is the only place that talks to the Pear/Holepunch stack:
//
//   corestore   - manages the raw append-only logs ("hypercores") on disk
//                 that everything else is built on top of.
//   hyperdrive  - a filesystem-like data structure (files + folders) stored
//                 as a hypercore. It gives us .put()/.get()/.list()/.diff()
//                 and, crucially, versioning: every write is a new version.
//   hyperswarm  - peer-to-peer networking. swarm.join(topic) announces the
//                 topic on the Kademlia DHT (Distributed Hash Table) and/or
//                 looks up other peers announcing that same topic, then
//                 opens direct encrypted connections to them.
//   localdrive  - wraps an ordinary local folder so it exposes the SAME
//                 interface as a hyperdrive. That means we can "mirror"
//                 local-folder <-> hyperdrive in either direction with the
//                 exact same call.
// ---------------------------------------------------------------------------
const fs = require('fs')
const path = require('path')
const Corestore = require('corestore')
const Hyperdrive = require('hyperdrive')
const Hyperswarm = require('hyperswarm')
const Localdrive = require('localdrive')
const b4a = require('b4a')
const registry = require('./registry')

// -- helpers ----------------------------------------------------------------

// A drive's public key is what you hand to another person so they can find
// and replicate your data over the DHT. We store/print it as hex.
function keyToHex (key) { return b4a.toString(key, 'hex') }
function hexToKey (hex) { return b4a.from(hex, 'hex') }

// Open (or create) a Hyperdrive backed by a Corestore rooted at `storageDir`.
// - If `remoteKeyHex` is omitted: Hyperdrive(store) with no key makes/reuses
//   OUR OWN writable drive. Corestore persists the keypair in storageDir, so
//   calling this again later against the same folder reopens the identical
//   drive with the identical public key.
// - If `remoteKeyHex` is given: Hyperdrive(store, key) opens a (read-only,
//   to us) replica of someone else's drive, identified by their public key.
async function openDrive (storageDir, remoteKeyHex) {
  const store = new Corestore(storageDir)
  const drive = remoteKeyHex
    ? new Hyperdrive(store, hexToKey(remoteKeyHex))
    : new Hyperdrive(store)
  await drive.ready()
  return { store, drive }
}

// Closing just the Hyperdrive is not enough - the Corestore it sits on top
// of holds its own file handles/locks open on storageDir. Since each CLI
// command is a short-lived process that opens the store fresh, we always
// close both, otherwise a later command touching the same storageDir in the
// same process (or, on some platforms, even a subsequent process) can fail
// with a "File descriptor could not be locked" error.
async function closeDrive ({ store, drive }) {
  await drive.close()
  await store.close()
}

// Join the DHT for a drive's discovery key and wire up replication.
// discoveryKey is a hash derived from the drive's public key - it's what
// actually gets announced on the DHT, so peers can find each other without
// exposing the real public key to random DHT nodes.
// mode: { server: true }  -> announce ourselves as a source of this data (seeding)
//       { client: true }  -> look up peers who are announcing it (pulling)
async function joinSwarm (store, drive, { server, client }) {
  const swarm = new Hyperswarm()
  // Whenever hyperswarm hands us a new peer connection, replicate our
  // corestore over it. Replication is what actually streams hypercore
  // blocks (file data + the drive's internal index) between peers.
  swarm.on('connection', (conn) => store.replicate(conn))
  const discoveryDone = drive.findingPeers()
  swarm.join(drive.discoveryKey, { server: !!server, client: !!client })
  await swarm.flush() // resolves once our announce/lookup round has gone out
  discoveryDone()
  return swarm
}

// -- public operations --------------------------------------------------

// Use case: "Alice/Bob creates a new hyperdrive and gets a public key"
async function create (name) {
  const storageDir = registry.storagePathFor(name)
  const opened = await openDrive(storageDir)
  const keyHex = keyToHex(opened.drive.key)
  registry.upsert(name, { role: 'own', storageDir, key: keyHex })
  await closeDrive(opened)
  return keyHex
}

// Use case: "Alice/Bob adds the contents of a specified directory to her/his
// hyperdrive". We wrap the local folder in a Localdrive and mirror it INTO
// the Hyperdrive. Hyperdrive.mirror() (called from the source side) walks
// the source, diffs it against the destination, and writes only what
// changed - each write becomes part of a new hyperdrive version.
async function addDirectory (name, sourceDir) {
  const entry = requireOwn(name)
  const opened = await openDrive(entry.storageDir)
  const src = new Localdrive(path.resolve(sourceDir))
  const mirror = src.mirror(opened.drive)
  await mirror.done()
  const result = { version: opened.drive.version, files: mirror.count.files }
  await closeDrive(opened)
  return result
}

// Use case: "Alice adds a file to her hyperdrive. This creates a new
// version." A single drive.put() appends new blocks to the drive's
// hypercore, which bumps drive.version - hyperdrives are versioned like
// git commits, one version per batch of writes.
async function addFile (name, localFilePath, drivePath) {
  const entry = requireOwn(name)
  const opened = await openDrive(entry.storageDir)
  const data = fs.readFileSync(localFilePath)
  const dest = drivePath || ('/' + path.basename(localFilePath))
  await opened.drive.put(dest, data)
  const version = opened.drive.version
  await closeDrive(opened)
  return { version, dest }
}

// Extract a single file from ANY known drive (our own, or a pulled replica)
// out to the normal filesystem. Used for the "Bob copies a file from
// Alice's hyperdrive" / "Alice retrieves the file with Bob's comments"
// steps - the actual copy is one drive.get() read + one fs.writeFile.
async function getFile (name, drivePath, localDestPath) {
  const entry = registry.get(name)
  if (!entry) throw new Error(`Unknown drive "${name}". Run "list" to see known drives.`)
  const opened = await openDrive(entry.storageDir, entry.role === 'remote' ? entry.key : undefined)
  const data = await opened.drive.get(drivePath)
  if (!data) { await closeDrive(opened); throw new Error(`"${drivePath}" not found in drive "${name}"`) }
  fs.mkdirSync(path.dirname(path.resolve(localDestPath)), { recursive: true })
  fs.writeFileSync(localDestPath, data)
  await closeDrive(opened)
  return localDestPath
}

// Use case: "Alice/Bob seeds her/his hyperdrive to the DHT".
// Joining as { server: true, client: true } announces the drive's
// discovery key on the DHT and keeps the process running so it can accept
// incoming replication connections from anyone who looks that key up -
// this is what makes the data "seeded" and pull-able by others.
async function seed (name) {
  const entry = requireOwn(name)
  const { store, drive } = await openDrive(entry.storageDir)
  const swarm = await joinSwarm(store, drive, { server: true, client: true })
  console.log(`Seeding "${name}"`)
  console.log(`  public key : ${keyToHex(drive.key)}`)
  console.log(`  version    : ${drive.version}`)
  console.log('  Announced on the DHT. Leave this running so peers can connect. Ctrl+C to stop.')
  // Keep the process alive; clean up the swarm/corestore on exit.
  const shutdown = async () => { await swarm.destroy(); await closeDrive({ store, drive }); process.exit(0) }
  process.on('SIGINT', shutdown)
  process.on('SIGTERM', shutdown)
  await new Promise(() => {}) // never resolves - process stays up until Ctrl+C
}

// Use case: "Bob pulls the latest version of Alice's hyperdrive to a
// specified (empty) directory" - and later, "to the same directory" again.
// We open (or reopen) a replica keyed to Alice's public key, join the DHT
// as a client to find her seeding process, ask the drive to fetch the
// latest state from the network, then mirror hyperdrive -> local folder
// (the reverse direction of addDirectory).
async function pull (name, remoteKeyHex, destDir) {
  const existing = registry.get(name)
  const keyHex = remoteKeyHex || (existing && existing.key)
  if (!keyHex) throw new Error('No public key known for this drive name; supply one.')
  const storageDir = (existing && existing.storageDir) || registry.storagePathFor(name)
  const { store, drive } = await openDrive(storageDir, keyHex)

  const swarm = await joinSwarm(store, drive, { client: true })
  // Pull the latest hypercore blocks (including any newer version pointer)
  // from whichever peers we found. `update` resolves once the drive's
  // metadata is caught up with what peers have.
  await drive.update({ wait: true }).catch(() => {}) // no-op if nobody's online yet
  fs.mkdirSync(path.resolve(destDir), { recursive: true })
  const dest = new Localdrive(path.resolve(destDir))
  const mirror = drive.mirror(dest)
  await mirror.done()

  registry.upsert(name, {
    role: 'remote',
    storageDir,
    key: keyHex,
    pullDir: path.resolve(destDir),
    lastVersion: drive.version
  })

  const result = { version: drive.version, files: mirror.count.files, destDir: path.resolve(destDir) }
  await swarm.destroy()
  await closeDrive({ store, drive })
  return result
}

// Use case: "Bob compares the version of Alice's hyperdrive against the
// version of his copy of it." We briefly join the DHT to refresh our view
// of the drive's latest version (without necessarily downloading file
// contents), then compare that live version number against the version we
// recorded the last time we pulled, and list which paths changed via
// drive.diff(oldVersion, prefix) - which yields { left, right } pairs where
// left is the entry in the current/live version and right is the entry as
// it was at oldVersion (added: left only, deleted: right only, modified: both).
async function diff (name) {
  const entry = registry.get(name)
  if (!entry || entry.role !== 'remote') throw new Error(`"${name}" is not a pulled remote drive.`)
  const { store, drive } = await openDrive(entry.storageDir, entry.key)
  const swarm = await joinSwarm(store, drive, { client: true })
  await drive.update({ wait: true }).catch(() => {})
  const remoteVersion = drive.version
  const localVersion = entry.lastVersion || 0

  const changes = []
  if (remoteVersion !== localVersion) {
    for await (const change of drive.diff(localVersion, '/')) {
      changes.push(change)
    }
  }
  await swarm.destroy()
  await closeDrive({ store, drive })
  return { localVersion, remoteVersion, upToDate: remoteVersion === localVersion, changes }
}

async function info (name) {
  const entry = registry.get(name)
  if (!entry) throw new Error(`Unknown drive "${name}"`)
  // The public key never changes once a drive exists, so we can answer that
  // part straight from our own registry without touching the corestore at
  // all. This matters because a corestore's on-disk storage can only be
  // opened by one process at a time (e.g. while "seed" is running) - we
  // don't want "info" to fail just because the drive is currently seeding.
  const out = { name, role: entry.role, key: entry.key, storageDir: entry.storageDir, pullDir: entry.pullDir, version: null }
  try {
    const opened = await openDrive(entry.storageDir, entry.role === 'remote' ? entry.key : undefined)
    out.version = opened.drive.version
    await closeDrive(opened)
  } catch (err) {
    out.versionUnavailable = 'storage is currently locked by another running ftlbox process (e.g. "seed")'
  }
  return out
}

function list () { return registry.all() }

function requireOwn (name) {
  const entry = registry.get(name)
  if (!entry || entry.role !== 'own') throw new Error(`"${name}" is not one of your own writable drives. Run "create" first.`)
  return entry
}

module.exports = {
  create, addDirectory, addFile, getFile, seed, pull, diff, info, list, keyToHex,
  // exposed for the test harness (test/full-flow.js), which needs to keep
  // Alice's and Bob's drives "seeding" concurrently inside one Node process -
  // real usage never needs these directly, since each CLI command is its
  // own process.
  openDrive, closeDrive, joinSwarm
}
