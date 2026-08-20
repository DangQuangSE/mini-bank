#!/usr/bin/env node
"use strict";

// PreCompact guard: only auto-compaction configured at 90% may proceed.

const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const REQUIRED_PERCENT = 90;
const USAGE_TTL_MS = 15_000;
const MAX_FUTURE_SKEW_MS = 1_000;

function block(reason) {
  return { decision: "block", reason };
}

function usagePath(sessionId) {
  if (typeof sessionId !== "string" || !/^[A-Za-z0-9._-]+$/.test(sessionId)) {
    return null;
  }
  return path.join(__dirname, "..", "session-data", `context-usage-${sessionId}.json`);
}

function trackUsage(payload) {
  const target = usagePath(payload && payload.session_id);
  if (!target) {
    return null;
  }

  const value = payload?.context_window?.used_percentage;
  const percent = typeof value === "number" && Number.isFinite(value) ? value : null;
  fs.mkdirSync(path.dirname(target), { recursive: true });
  const temporary = `${target}.${process.pid}.tmp`;
  fs.writeFileSync(
    temporary,
    JSON.stringify({
      session_id: payload.session_id,
      used_percentage: percent,
      observed_at: Date.now(),
    }),
    "utf8"
  );
  fs.renameSync(temporary, target);
  return percent;
}

function readUsage(sessionId) {
  const target = usagePath(sessionId);
  if (!target) {
    return null;
  }
  try {
    const record = JSON.parse(fs.readFileSync(target, "utf8"));
    const now = Date.now();
    const observedAt = record.observed_at;
    if (
      typeof observedAt !== "number" ||
      !Number.isFinite(observedAt) ||
      observedAt > now + MAX_FUTURE_SKEW_MS ||
      now - observedAt > USAGE_TTL_MS
    ) {
      return null;
    }
    if (
      typeof record.used_percentage !== "number" ||
      !Number.isFinite(record.used_percentage)
    ) {
      return null;
    }
    return record.used_percentage;
  } catch (_error) {
    return null;
  }
}

function decide(
  payload,
  configuredPercent = process.env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE,
  observedPercent = readUsage(payload && payload.session_id)
) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return block("Compaction blocked: invalid PreCompact payload.");
  }

  const percent = Number(configuredPercent);
  if (!Number.isFinite(percent) || percent !== REQUIRED_PERCENT) {
    return block(
      "Compaction blocked: CLAUDE_AUTOCOMPACT_PCT_OVERRIDE must be exactly 90."
    );
  }

  if (!['auto', 'manual'].includes(payload.trigger)) {
    return block(
      "Compaction blocked: unsupported PreCompact trigger."
    );
  }

  if (
    typeof observedPercent !== "number" ||
    !Number.isFinite(observedPercent) ||
    observedPercent < REQUIRED_PERCENT
  ) {
    const shown = Number.isFinite(observedPercent)
      ? `${observedPercent.toFixed(1)}%`
      : "unknown";
    return block(
      `Compaction blocked: session context is ${shown}; at least 90% is required.`
    );
  }

  return null;
}

function savePreCompactState(rawInput) {
  const runner = path.join(__dirname, "run.js");
  const saver = path.join(__dirname, "pre_compact.py");
  const result = spawnSync(process.execPath, [runner, saver], {
    input: rawInput,
    encoding: "utf8",
    windowsHide: true,
    timeout: 4500,
  });

  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(
      `pre-compact state save failed with exit code ${result.status}: ${
        (result.stderr || "").trim() || "no error output"
      }`
    );
  }
}

function emitBlock(reason) {
  process.stdout.write(JSON.stringify(block(reason)));
}

function main() {
  let rawInput = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (chunk) => {
    rawInput += chunk;
  });
  process.stdin.on("end", () => {
    try {
      const payload = JSON.parse(rawInput);
      const decision = decide(payload);
      if (decision) {
        process.stdout.write(JSON.stringify(decision));
        return;
      }

      // Used only by local verification; production settings omit this flag.
      if (!process.argv.includes("--decision-only")) {
        savePreCompactState(rawInput);
      }
    } catch (error) {
      emitBlock(`Compaction blocked: ${error.message || String(error)}`);
    }
  });
  process.stdin.resume();
}

function trackMain() {
  let rawInput = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (chunk) => {
    rawInput += chunk;
  });
  process.stdin.on("end", () => {
    try {
      const payload = JSON.parse(rawInput);
      const percent = trackUsage(payload);
      process.stdout.write(
        percent === null ? "Context --" : `Context ${percent.toFixed(0)}%`
      );
    } catch (_error) {
      process.stdout.write("Context --");
    }
  });
  process.stdin.resume();
}

if (require.main === module) {
  if (process.argv.includes("--track")) {
    trackMain();
  } else {
    main();
  }
}

module.exports = {
  decide,
  readUsage,
  savePreCompactState,
  trackUsage,
  usagePath,
  USAGE_TTL_MS,
};
