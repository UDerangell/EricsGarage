A demonstration of using the Pears.com stack to implement specific use cases for distributed file sharing:

Prompt to Claude Sonnet 5: 
- Please code a terminal application named FTLBOX that uses [Pears.com](http://pears.com/) to give the user a command line interface that supports the following use cases:
  - Alice creates a new hyperdrive and gets a public key
  - Alice adds the contents of a specified directory to her hyperdrive
  - Alice seeds her hyperdrive to the DHT
  - Alice sends Bob her public key (outside the scope of this system)
  - Bob creates a new hyperdrive and gets a public key
  - Bob adds the contents of a specified directory to his hyperdrive
  - Bob seeds his hyperdrive to the DHT
  - Bob sends Alice his public key (outside the scope of this system)
  - Bob pulls the latest version of Alice's hyperdrive to a specified empty directory on his computer
  - Alice adds a file to her hyperdrive.  This creates a new version of the hyperdrive.
  - Bob compares the version of Alice's hyperdrive against the verson of his copy of it.
  - Bob pulls the latest version of Alice's hyperdrive to the same directory he used when it was first downloaded.
  - Bob copies a file from Alice's hyperdrive to his own hyperdrive (outside the scope of this system)
  - Bob edits that file and adds comments for Alice to review. (outside the scope of this system)
  - Alice pulls the latest version of Bob's hyperdrive and retrieves the file with Bob's comments.
- Indicate exactly how Alice and Bob would install this application and execute the use cases described above.
- Please comment each section of code to explain how it is using Pears to accomplish its task.

Sample output: 
```
node bin/ftlbox.js

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

node bin/ftlbox.js create ericdrv
Created drive "ericdrv"
Public key: dc53426b9f5e3a1a55f7609921c7002292f7998e79ecf51337f999c1939700be
Share this key with your peer so they can pull this drive.

node bin/ftlbox.js add ericdrv ~/Downloads/git/4FTL
Added contents of "/Users/ericrangell/Downloads/git/4FTL" to "ericdrv" -> version 2 (1 file(s) written/updated)

node bin/ftlbox.js list               
ericdrv  [own]  key=dc53426b9f5e3a1a55f7609921c7002292f7998e79ecf51337f999c1939700be  


node bin/ftlbox.js seed ericdrv
Seeding "ericdrv"
  public key : dc53426b9f5e3a1a55f7609921c7002292f7998e79ecf51337f999c1939700be
  version    : 2
  Announced on the DHT. Leave this running so peers can connect. Ctrl+C to stop.


node bin/ftlbox.js addfile ericdrv ~/Downloads/git/4FTL/test20260712.txt
Added "/Users/ericrangell/Downloads/git/4FTL/test20260712.txt" to "ericdrv" as "/test20260712.txt" -> new version 3

(Published another version, then pulled from a different machine)

node bin/ftlbox.js pull dc53426b9f5e3a1a55f7609921c7002292f7998e79ecf51337f999c1939700be ~/Downloads/git/4FTL/ericdrv-copy
Pulled "dc53426b" (version 4) into /Users/ericrangell/Downloads/git/4FTL/ericdrv-copy (2 file(s) written/updated)

ls -l /Users/ericrangell/Downloads/git/4FTL/ericdrv-copy
total 32
-rw-r--r--  1 ericrangell  staff  11770 Jul 12 21:37 liquid-documents-proposal.md
-rw-r--r--@ 1 ericrangell  staff   1980 Jul 12 21:37 test20260712.txt

```

