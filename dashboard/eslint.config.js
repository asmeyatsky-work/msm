// §2: layer direction enforced via eslint-plugin-boundaries.
import boundaries from "eslint-plugin-boundaries";

export default [
  {
    plugins: { boundaries },
    settings: {
      "boundaries/elements": [
        { type: "domain",         pattern: "src/domain/**" },
        { type: "application",    pattern: "src/application/**" },
        { type: "infrastructure", pattern: "src/infrastructure/**" },
        { type: "presentation",   pattern: "src/presentation/**" },
      ],
    },
    rules: {
      // domain ← application ← infrastructure, presentation
      "boundaries/element-types": ["error", {
        default: "disallow",
        rules: [
          { from: "domain",         allow: [] },
          { from: "application",    allow: ["domain"] },
          { from: "infrastructure", allow: ["domain", "application"] },
          { from: "presentation",   allow: ["domain", "application", "infrastructure"] },
        ],
      }],
    },
  },
];
