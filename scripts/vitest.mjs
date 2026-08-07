#!/usr/bin/env node
import { parseCLI, startVitest } from 'vitest/node'
import config, { testConfig } from './vitest.config.mjs'

const [command = 'run', ...argv] = process.argv.slice(2)
const { filter, options } = parseCLI(['vitest', ...argv])
const shouldRun = command !== 'watch'

await startVitest(
  'test',
  filter,
  {
    ...testConfig,
    ...options,
    run: shouldRun,
    coverage: command === 'coverage'
      ? { ...testConfig.coverage, ...options.coverage, enabled: true }
      : { ...testConfig.coverage, ...options.coverage },
  },
  {
    configFile: false,
    plugins: config.plugins,
    resolve: config.resolve,
    optimizeDeps: { noDiscovery: true, include: [] },
  },
)
