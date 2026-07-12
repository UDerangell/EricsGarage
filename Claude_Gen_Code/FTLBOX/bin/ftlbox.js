#!/usr/bin/env node
'use strict'
// FTLBOX command-line interface. This file only does argument parsing and
// printing - all the actual Pear/Hyperdrive/Hyperswarm work lives in
// lib/drive.js so it's easy to read in one place.
const drive = require('../lib/drive')

const HELP = `
FTLBOX - a peer-to-peer file drop built on the Pear (Holepunch) stack
(corestore + hyperdrive + hyperswarm)

Usage:
  ftlbox create <name>                       create a new writable hyperdrive
  ftlbox add <name> <dir>                    add a local directory's contents to your drive
  ftlbox addfile <name> <file> [drivePath]   add a single local file to your drive
  ftlbox get <name> <drivePath> <outFile>    extract one file from a drive (yours or a pulled one)
  ftlbox seed <name>                         announce your drive on the DHT and serve it (stays running)
  ftlbox pull <key> <destDir> [--name n]     pull a drive by its public key into destDir
  ftlbox diff <name>                         compare your pulled copy's version against the live one
  ftlbox info <name>                         show a drive's public key / version
  ftlbox list                                list all drives FTLBOX knows about
`

async function main () {
  const [cmd, ...rest] = process.argv.slice(2)
  try {
    switch (cmd) {
      case 'create': {
        const [name] = rest
        if (!name) throw new Error('usage: ftlbox create <name>')
        const key = await drive.create(name)
        console.log(`Created drive "${name}"`)
        console.log(`Public key: ${key}`)
        console.log(`Share this key with your peer so they can pull this drive.`)
        break
      }
      case 'add': {
        const [name, dir] = rest
        if (!name || !dir) throw new Error('usage: ftlbox add <name> <dir>')
        const r = await drive.addDirectory(name, dir)
        console.log(`Added contents of "${dir}" to "${name}" -> version ${r.version} (${r.files} file(s) written/updated)`)
        break
      }
      case 'addfile': {
        const [name, file, drivePath] = rest
        if (!name || !file) throw new Error('usage: ftlbox addfile <name> <file> [drivePath]')
        const r = await drive.addFile(name, file, drivePath)
        console.log(`Added "${file}" to "${name}" as "${r.dest}" -> new version ${r.version}`)
        break
      }
      case 'get': {
        const [name, drivePath, outFile] = rest
        if (!name || !drivePath || !outFile) throw new Error('usage: ftlbox get <name> <drivePath> <outFile>')
        const out = await drive.getFile(name, drivePath, outFile)
        console.log(`Wrote "${drivePath}" from "${name}" to ${out}`)
        break
      }
      case 'seed': {
        const [name] = rest
        if (!name) throw new Error('usage: ftlbox seed <name>')
        await drive.seed(name) // long-running; only returns on Ctrl+C
        break
      }
      case 'pull': {
        const [key, destDir] = rest
        if (!key || !destDir) throw new Error('usage: ftlbox pull <publicKeyHex> <destDir> [--name localName]')
        const nameFlagIdx = rest.indexOf('--name')
        const name = nameFlagIdx !== -1 ? rest[nameFlagIdx + 1] : key.slice(0, 8)
        const r = await drive.pull(name, key, destDir)
        console.log(`Pulled "${name}" (version ${r.version}) into ${r.destDir} (${r.files} file(s) written/updated)`)
        break
      }
      case 'diff': {
        const [name] = rest
        if (!name) throw new Error('usage: ftlbox diff <name>')
        const r = await drive.diff(name)
        if (r.upToDate) {
          console.log(`"${name}" is up to date (version ${r.localVersion}).`)
        } else {
          console.log(`"${name}": local copy is version ${r.localVersion}, latest on the network is version ${r.remoteVersion}.`)
          console.log('Changed paths:')
          for (const c of r.changes) {
            // hyperdrive.diff(oldVersion) entries are shaped { left, right }:
            //   left  = the entry as it exists in the CURRENT/live version
            //   right = the entry as it existed in oldVersion
            // So: left+right -> modified, left only -> added, right only -> deleted.
            const kind = c.left && c.right ? 'modified' : c.left ? 'added' : 'deleted'
            const key = (c.left || c.right).key
            console.log(`  ${kind.padEnd(8)} ${key}`)
          }
        }
        break
      }
      case 'info': {
        const [name] = rest
        if (!name) throw new Error('usage: ftlbox info <name>')
        const r = await drive.info(name)
        console.log(JSON.stringify(r, null, 2))
        break
      }
      case 'list': {
        const all = drive.list()
        if (Object.keys(all).length === 0) console.log('(no drives yet)')
        for (const [name, entry] of Object.entries(all)) {
          console.log(`${name}  [${entry.role}]  key=${entry.key}  ${entry.pullDir ? 'pullDir=' + entry.pullDir : ''}`)
        }
        break
      }
      default:
        console.log(HELP)
    }
  } catch (err) {
    console.error('Error:', err.message)
    process.exitCode = 1
  }
}

main()
