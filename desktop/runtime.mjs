import { randomBytes, randomInt } from "node:crypto";

export const DESKTOP_HEADER = "X-Zhiyu-Desktop-Token";
export const DESKTOP_HOST = "127.0.0.1";
export const MIN_DYNAMIC_PORT = 49152;
export const MAX_DYNAMIC_PORT = 65535;

export function createDesktopToken() {
  return randomBytes(32).toString("base64url");
}

export function selectPreferredPort() {
  return randomInt(MIN_DYNAMIC_PORT, MAX_DYNAMIC_PORT + 1);
}

export function isBackendUrl(urlText, port) {
  try {
    const url = new URL(urlText);
    return url.protocol === "http:" && url.hostname === DESKTOP_HOST && Number(url.port) === port;
  } catch {
    return false;
  }
}

export function desktopDatabaseUrl(dataDir) {
  const normalized = dataDir.replace(/\\/g, "/");
  return `sqlite:///${normalized}/app.db`;
}

export function parseListeningEvent(line) {
  try {
    const message = JSON.parse(line);
    if (
      message?.event === "desktop-listening" &&
      Number.isInteger(message.port) &&
      message.port >= MIN_DYNAMIC_PORT &&
      message.port <= MAX_DYNAMIC_PORT
    ) {
      return message.port;
    }
  } catch {
    // Back-end logs are allowed before the readiness event.
  }
  return null;
}
