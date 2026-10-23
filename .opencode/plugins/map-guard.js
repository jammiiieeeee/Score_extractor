import { readFileSync } from "node:fs"
import { join, relative, sep } from "node:path"

const MAP_FILE = "docs/agents/repo-map.md"
const WATCHED = ["src/", "tests/", "tools/", "scripts/"]

export const MapGuard = async ({ directory }) => {
  const mapPath = join(directory, MAP_FILE)

  const readMap = () => {
    try {
      return readFileSync(mapPath, "utf8")
    } catch {
      return ""
    }
  }

  return {
    "tool.execute.after": async (input, output) => {
      try {
        if (input.tool !== "write") return
        const filePath = input.args?.filePath
        if (typeof filePath !== "string" || filePath.length === 0) return

        const rel = relative(directory, filePath).split(sep).join("/")
        if (!WATCHED.some((prefix) => rel.startsWith(prefix))) return

        const stem = rel.split("/").pop().replace(/\.[^.]+$/, "")
        const map = readMap()
        if (map.includes(stem)) return

        // The map groups some files with prefixes, e.g. `test_gui_api*`.
        const prefixes = map.match(/[A-Za-z0-9_./-]+\*/g) ?? []
        if (prefixes.some((token) => stem.startsWith(token.slice(0, -1)))) return

        const note =
          `\n\n[MAP GUARD] ${rel} is not mentioned in ${MAP_FILE}. ` +
          `Add it to the module table and add a dated line under "Recently changed" ` +
          `before you finish, so the next session does not have to rescan.`

        if (typeof output.output === "string") output.output += note
      } catch {
        // A guard must never break the tool call.
      }
    },
  }
}
