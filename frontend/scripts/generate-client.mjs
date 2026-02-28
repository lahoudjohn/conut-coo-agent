import { execSync } from "node:child_process";

const source = process.env.OPENAPI_URL || "http://backend:8000/openapi.json";
const target = "./src/types/api.d.ts";

execSync(`npx openapi-typescript ${source} -o ${target}`, { stdio: "inherit" });
console.log(`Generated client types from ${source} -> ${target}`);
