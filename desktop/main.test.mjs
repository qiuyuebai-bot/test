import assert from "node:assert/strict";
import test from "node:test";

import {
  DESKTOP_HOST,
  MAX_DYNAMIC_PORT,
  MIN_DYNAMIC_PORT,
  createDesktopToken,
  desktopDatabaseUrl,
  isBackendUrl,
  parseListeningEvent,
  selectPreferredPort,
} from "./runtime.mjs";

test("desktop token is non-empty and changes between runs", () => {
  const first = createDesktopToken();
  const second = createDesktopToken();
  assert.ok(first.length >= 32);
  assert.notEqual(first, second);
});

test("preferred port stays inside the dynamic private range", () => {
  const port = selectPreferredPort();
  assert.ok(port >= MIN_DYNAMIC_PORT && port <= MAX_DYNAMIC_PORT);
});

test("only the selected loopback backend origin is trusted", () => {
  const port = 51234;
  assert.equal(isBackendUrl(`http://${DESKTOP_HOST}:${port}/api/v1/health/live`, port), true);
  assert.equal(isBackendUrl(`http://localhost:${port}/`, port), false);
  assert.equal(isBackendUrl(`https://${DESKTOP_HOST}:${port}/`, port), false);
  assert.equal(isBackendUrl(`http://${DESKTOP_HOST}:51235/`, port), false);
});

test("backend reports only valid listening events", () => {
  assert.equal(parseListeningEvent('{"event":"desktop-listening","port":51234}'), 51234);
  assert.equal(parseListeningEvent('{"event":"desktop-listening","port":8000}'), null);
  assert.equal(parseListeningEvent("not json"), null);
});

test("desktop database URL keeps Windows paths valid for SQLAlchemy", () => {
  assert.equal(
    desktopDatabaseUrl("C:\\Users\\example\\AppData\\Roaming\\知域引擎\\data"),
    "sqlite:///C:/Users/example/AppData/Roaming/知域引擎/data/app.db",
  );
});
