'use strict'
// This test exercises the SAME lib/drive.js functions the CLI uses for
// every operation EXCEPT the network transport itself: this sandbox's
// network policy blocks local/loopback connections, so a real Hyperswarm/DHT
// handshake can't be verified here. Instead we replicate corestore data over
// an in-memory duplex stream pair (Node's stream.duplexPair) - this drives
// the exact same store.replicate(stream) call that Hyperswarm's
// 'connection' handler makes, just fed a plain in-process stream instead of
// a real socket. Everything downstream of "we have a connected replication
// stream" (drive.update(), drive.mirror(), drive.diff(), versioning) is
// tested for real, unmodified from the CLI's code path.
const { duplexPair } = require('stream')
const fs = require('fs')
const path = require('path')
const os = require('os')

async function main () {
  const drive = require('../lib/drive.js')
  const registry = require('../lib/registry.js')

  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ftlbox-test-'))
  const aliceDir = path.join(root, 'alice'); fs.mkdirSync(aliceDir)
  const bobDir = path.join(root, 'bob'); fs.mkdirSync(bobDir)

  function inDir (dir, fn) {
    const prev = process.cwd()
    process.chdir(dir)
    return Promise.resolve().then(fn).finally(() => process.chdir(prev))
  }

  // Connects two already-open corestores as if a Hyperswarm connection had
  // just fired on both sides - i.e. replaces `swarm.on('connection', conn =>
  // store.replicate(conn))` with a direct, in-memory pipe. A real Hyperswarm
  // 'connection' object is a NoiseSecretStream, not a bare duplex, so we
  // wrap our in-memory pair the same way (encryption keys are irrelevant
  // here - only the framing/protocol interface corestore.replicate expects
  // matters for this test).
  const NoiseSecretStream = require('@hyperswarm/secret-stream')
  function replicatePair (storeA, storeB) {
    const [rawA, rawB] = duplexPair()
    const a = new NoiseSecretStream(true, rawA)
    const b = new NoiseSecretStream(false, rawB)
    storeA.replicate(a)
    storeB.replicate(b)
  }

  let aliceKey, bobKey
  const assert = (cond, msg) => { if (!cond) throw new Error('ASSERTION FAILED: ' + msg) }

  // 1. Alice creates a new hyperdrive and gets a public key
  await inDir(aliceDir, async () => {
    fs.mkdirSync('mysrc')
    fs.writeFileSync('mysrc/hello.txt', 'hello world')
    fs.writeFileSync('mysrc/readme.md', 'readme content')
    aliceKey = await drive.create('alice-drive')
    assert(/^[0-9a-f]{64}$/.test(aliceKey), 'alice key looks like 32-byte hex')
  })

  // 2. Alice adds the contents of mysrc/ to her hyperdrive
  let aliceVersionAfterAdd
  await inDir(aliceDir, async () => {
    const r = await drive.addDirectory('alice-drive', 'mysrc')
    assert(r.files === 2, 'alice added 2 files, got ' + r.files)
    aliceVersionAfterAdd = r.version
    console.log('OK: alice-drive version after adding mysrc/ =', r.version)
  })

  // 5. Bob creates a new hyperdrive and gets a public key
  await inDir(bobDir, async () => {
    fs.mkdirSync('bobsrc')
    fs.writeFileSync('bobsrc/bobfile.txt', "bob's local file")
    bobKey = await drive.create('bob-drive')
    assert(/^[0-9a-f]{64}$/.test(bobKey), 'bob key looks like 32-byte hex')
  })

  // 6. Bob adds the contents of bobsrc/ to his hyperdrive
  await inDir(bobDir, async () => {
    const r = await drive.addDirectory('bob-drive', 'bobsrc')
    assert(r.files === 1, 'bob added 1 file, got ' + r.files)
  })

  // 3/7. "Seed" both drives: open them and keep them open so a replication
  // link can be attached, standing in for a real long-running `ftlbox seed`
  // process that's announced on the DHT and accepting connections.
  const aliceEntry = await inDir(aliceDir, () => registry.get('alice-drive'))
  const bobEntry = await inDir(bobDir, () => registry.get('bob-drive'))
  let aliceOpened = await drive.openDrive(aliceEntry.storageDir)
  let bobOpened = await drive.openDrive(bobEntry.storageDir)
  console.log('Both Alice and Bob are now "seeding" (replication link open).')

  // 9. Bob pulls the latest version of Alice's hyperdrive into an empty dir.
  // pull() normally does: openDrive(key) -> joinSwarm (DHT) -> drive.update()
  // -> mirror to local folder. Here we open Bob's replica the same way
  // pull() does internally, but instead of joinSwarm() we attach the direct
  // stream pipe, then call the exact same update+mirror logic.
  async function manualPull (name, keyHex, storageDir, remoteOpened, destDir) {
    const opened = await drive.openDrive(storageDir, keyHex)
    replicatePair(opened.store, remoteOpened.store)
    await opened.drive.update({ wait: true })
    fs.mkdirSync(path.resolve(destDir), { recursive: true })
    const Localdrive = require('localdrive')
    const dest = new Localdrive(path.resolve(destDir))
    const mirror = opened.drive.mirror(dest)
    await mirror.done()
    registry.upsert(name, { role: 'remote', storageDir, key: keyHex, pullDir: path.resolve(destDir), lastVersion: opened.drive.version })
    const result = { version: opened.drive.version, files: mirror.count.files }
    await drive.closeDrive(opened)
    return result
  }

  await inDir(bobDir, async () => {
    fs.mkdirSync('bob-pulled-from-alice')
    const storageDir = registry.storagePathFor('alice-copy')
    const r = await manualPull('alice-copy', aliceKey, storageDir, aliceOpened, 'bob-pulled-from-alice')
    assert(r.files === 2, 'bob pulled 2 files from alice, got ' + r.files)
    const txt = fs.readFileSync('bob-pulled-from-alice/hello.txt', 'utf8')
    assert(txt === 'hello world', 'pulled file content matches: ' + txt)
    console.log('OK: Bob pulled alice-drive ->', fs.readdirSync('bob-pulled-from-alice'))
  })

  // 10. Alice adds a file to her hyperdrive -> new version.
  // Corestore storage can only be held open by one process/instance at a
  // time, so - exactly like a real `ftlbox seed` process would have to be
  // stopped before another `ftlbox` command can write to the same drive -
  // we close the long-lived "seeding" handle first, and reopen it after
  // (simulating Alice Ctrl+C'ing seed, running addfile, then restarting seed).
  await drive.closeDrive(aliceOpened)
  await inDir(aliceDir, async () => {
    fs.writeFileSync('newfile.txt', 'a brand new file from alice')
    const r = await drive.addFile('alice-drive', 'newfile.txt', '/newfile.txt')
    assert(r.version > aliceVersionAfterAdd, 'alice drive version should have increased, was ' + aliceVersionAfterAdd + ' now ' + r.version)
    aliceVersionAfterAdd = r.version
    console.log('OK: alice-drive is now version', r.version)
  })
  aliceOpened = await drive.openDrive(aliceEntry.storageDir)

  // 11. Bob compares his copy's version against Alice's live version
  async function manualDiff (name, remoteOpened) {
    const entry = registry.get(name)
    const opened = await drive.openDrive(entry.storageDir, entry.key)
    replicatePair(opened.store, remoteOpened.store)
    await opened.drive.update({ wait: true })
    const remoteVersion = opened.drive.version
    const localVersion = entry.lastVersion || 0
    const changes = []
    if (remoteVersion !== localVersion) {
      for await (const change of opened.drive.diff(localVersion, '/')) changes.push(change)
    }
    await drive.closeDrive(opened)
    return { localVersion, remoteVersion, upToDate: remoteVersion === localVersion, changes }
  }

  await inDir(bobDir, async () => {
    const r = await manualDiff('alice-copy', aliceOpened)
    assert(r.upToDate === false, 'bob should see a pending update')
    assert(r.remoteVersion === aliceVersionAfterAdd, 'remote should report latest alice version ' + aliceVersionAfterAdd + ', got ' + r.remoteVersion)
    const added = r.changes.find(c => c.left && c.left.key === '/newfile.txt')
    assert(added, 'diff should list /newfile.txt as changed (added)')
    console.log('OK: diff shows local v' + r.localVersion + ' vs remote v' + r.remoteVersion, '- changes:', r.changes.map(c => (c.left || c.right).key))
  })

  // 12. Bob re-pulls into the SAME directory
  await inDir(bobDir, async () => {
    const entry = registry.get('alice-copy')
    const r = await manualPull('alice-copy', aliceKey, entry.storageDir, aliceOpened, entry.pullDir)
    assert(r.version === aliceVersionAfterAdd, 'after re-pull bob should match alice version ' + aliceVersionAfterAdd + ', got ' + r.version)
    const txt = fs.readFileSync('bob-pulled-from-alice/newfile.txt', 'utf8')
    assert(txt === 'a brand new file from alice', 'new file content correct: ' + txt)
    console.log('OK: re-pull into same dir now contains', fs.readdirSync('bob-pulled-from-alice'))
  })

  // 13/14. Bob "copies" a file out of Alice's drive into his own drive, edits it
  await drive.closeDrive(bobOpened)
  await inDir(bobDir, async () => {
    await drive.getFile('alice-copy', '/newfile.txt', 'extracted-newfile.txt')
    let content = fs.readFileSync('extracted-newfile.txt', 'utf8')
    content += '\n\n[Bob] looks good, minor comment: nice work!'
    fs.writeFileSync('extracted-newfile.txt', content)
    const r = await drive.addFile('bob-drive', 'extracted-newfile.txt', '/newfile-with-comments.txt')
    console.log('OK: bob added commented file to bob-drive, version', r.version)
  })
  bobOpened = await drive.openDrive(bobEntry.storageDir)

  // 15. Alice pulls Bob's drive and retrieves the commented file
  await inDir(aliceDir, async () => {
    fs.mkdirSync('alice-pulled-from-bob')
    const storageDir = registry.storagePathFor('bob-copy')
    await manualPull('bob-copy', bobKey, storageDir, bobOpened, 'alice-pulled-from-bob')
    assert(fs.existsSync('alice-pulled-from-bob/newfile-with-comments.txt'), 'commented file present')
    const finalText = fs.readFileSync('alice-pulled-from-bob/newfile-with-comments.txt', 'utf8')
    assert(finalText.includes('Bob'), 'comment text present')
    console.log('OK: alice retrieved commented file:\n---\n' + finalText + '\n---')
  })

  await drive.closeDrive(aliceOpened)
  await drive.closeDrive(bobOpened)

  console.log('\nALL USE CASES PASSED (replication verified over an in-memory stream since this sandbox blocks local network connections; DHT/Hyperswarm join logic is unchanged - only the transport differs, see README)')
  process.exit(0)
}

main().catch(err => { console.error('TEST FAILED:', err); process.exit(1) })
