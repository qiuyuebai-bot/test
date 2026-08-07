// Vite's CLI bundles TypeScript config files with esbuild. On Windows hosts where
// parent folders are access-restricted, that scan can fail before Vite starts.
// Keep this typed entry for editor support; npm scripts load the same config
// directly from the native ESM module in scripts/vite.config.mjs.
// @ts-expect-error The runtime config is a JavaScript ESM module.
export { default } from './scripts/vite.config.mjs'
