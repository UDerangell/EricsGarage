import express from "express";
import * as path from "path";
import { Auth } from "./auth";
import { createStructuresRouter } from "./routes/structures";
import { Store } from "./store";

const PORT = Number(process.env.PORT ?? 3000);
const DATA_DIR = process.env.ZZ_DATA_DIR
  ? path.resolve(process.env.ZZ_DATA_DIR)
  : path.resolve(__dirname, "..", "data");
const AUTHORIZATION_PATH = path.join(DATA_DIR, "authorization.json");

function main(): void {
  const auth = Auth.loadFromFile(AUTHORIZATION_PATH);
  const store = Store.initialize(auth, DATA_DIR);

  const app = express();
  app.use(express.json());
  app.use(createStructuresRouter(store, auth));

  app.use((_req, res) => {
    res.status(404).json({ error: "not_found" });
  });

  app.listen(PORT, () => {
    console.log(`zzStructure POC API listening on http://localhost:${PORT}`);
    console.log(`Data directory: ${DATA_DIR}`);
    for (const user of auth.users) {
      console.log(`  ${user.displayName}: ${user.id} -> ${user.dataFile}`);
    }
  });
}

main();
