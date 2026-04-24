// §2: layer direction enforced via eslint-plugin-boundaries.
import boundaries from "eslint-plugin-boundaries";
import tseslint from "typescript-eslint";

export default [
  ...tseslint.configs.base,
  {
    files: ["src/**/*.ts", "src/**/*.tsx"],
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        ecmaFeatures: { jsx: true },
      },
    },
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
