import { afterEach, describe, expect, it } from "vitest";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { loadSecret, MissingSecretError, verifySessionToken } from "./session";

// Minted once with the Python bridge:
//   sign_token("fixture-secret-for-tests", 1800, now=1700000000)
const SECRET = "fixture-secret-for-tests";
const TOKEN =
  "eyJzdWIiOiJmYWNlLTEiLCJleHAiOjE3MDAwMDE4MDAsImp0aSI6IkFJNE1TeC02T3VKMUhnQUcifQ.qlv8DMqUe7jOxAKZQWQnCTjtJ1txislvfOsU1CYvWNU";
const EXP = 1700001800;

describe("verifySessionToken", () => {
  it("accepts a token signed by the Python bridge", () => {
    const payload = verifySessionToken(TOKEN, SECRET, EXP - 60);
    expect(payload).toMatchObject({ sub: "face-1", exp: EXP });
  });

  it("rejects an expired token", () => {
    expect(verifySessionToken(TOKEN, SECRET, EXP)).toBeNull();
    expect(verifySessionToken(TOKEN, SECRET, EXP + 1)).toBeNull();
  });

  it("rejects a tampered payload", () => {
    const [body, signature] = TOKEN.split(".");
    const forged = Buffer.from(
      JSON.stringify({ sub: "face-1", exp: EXP + 99999, jti: "x" }),
    ).toString("base64url");
    expect(verifySessionToken(`${forged}.${signature}`, SECRET, EXP - 60)).toBeNull();
    const flipped = body.slice(0, -1) + (body.endsWith("A") ? "B" : "A");
    expect(verifySessionToken(`${flipped}.${signature}`, SECRET, EXP - 60)).toBeNull();
  });

  it("rejects a tampered signature", () => {
    const [body, signature] = TOKEN.split(".");
    const flipped = (signature.startsWith("A") ? "B" : "A") + signature.slice(1);
    expect(verifySessionToken(`${body}.${flipped}`, SECRET, EXP - 60)).toBeNull();
  });

  it("rejects the wrong secret", () => {
    expect(verifySessionToken(TOKEN, "another-secret", EXP - 60)).toBeNull();
  });

  it("rejects malformed input", () => {
    for (const bad of [undefined, null, "", "abc", "a.b.c", "a.b!", `${TOKEN}.`]) {
      expect(verifySessionToken(bad, SECRET, EXP - 60)).toBeNull();
    }
  });
});

describe("loadSecret", () => {
  const original = process.env.HUENIT_SESSION_SECRET;
  afterEach(() => {
    if (original === undefined) delete process.env.HUENIT_SESSION_SECRET;
    else process.env.HUENIT_SESSION_SECRET = original;
  });

  it("prefers the environment variable", () => {
    process.env.HUENIT_SESSION_SECRET = "  from-env  ";
    expect(loadSecret("does-not-exist")).toBe("from-env");
  });

  it("reads and trims the shared file", () => {
    delete process.env.HUENIT_SESSION_SECRET;
    const file = path.join(mkdtempSync(path.join(tmpdir(), "huenit-")), ".session_secret");
    writeFileSync(file, "abc123\n");
    expect(loadSecret(file)).toBe("abc123");
  });

  it("fails closed when the file is missing", () => {
    delete process.env.HUENIT_SESSION_SECRET;
    expect(() => loadSecret(path.join(tmpdir(), "missing-huenit-secret"))).toThrow(MissingSecretError);
  });
});
