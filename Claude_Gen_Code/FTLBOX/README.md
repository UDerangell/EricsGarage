A demonstration of using the Pears.com stack to implement specific use cases for distributed file sharing:

Prompt: ```
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

```
