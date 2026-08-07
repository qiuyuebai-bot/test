#!/usr/bin/env node
import { build, createServer, preview } from 'vite'
import config from './vite.config.mjs'

const [command = 'dev', mode] = process.argv.slice(2)
const inlineConfig = { ...config, configFile: false, ...(mode ? { mode } : {}) }

if (command === 'dev') {
  const server = await createServer(inlineConfig)
  await server.listen()
  server.printUrls()
} else if (command === 'serve') {
  await build(inlineConfig)
  const server = await preview(inlineConfig)
  server.printUrls()
} else if (command === 'build') {
  await build(inlineConfig)
} else if (command === 'preview') {
  const server = await preview(inlineConfig)
  server.printUrls()
} else {
  console.error(`Unknown Vite command: ${command}`)
  process.exitCode = 1
}
