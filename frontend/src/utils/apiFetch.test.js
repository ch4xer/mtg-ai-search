import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiFetch, apiJson } from "./apiFetch.js";

const storage = new Map();

beforeEach(() => {
  storage.clear();
  vi.stubGlobal("localStorage", {
    getItem: (key) => storage.get(key) || null,
    setItem: (key, value) => storage.set(key, value),
    removeItem: (key) => storage.delete(key),
  });
});

describe("apiFetch", () => {
  it("serializes JSON without mutating the caller's options", async () => {
    const options = { method: "POST", body: { query: "draw cards" } };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status: 200 }));

    await apiFetch("/api/search", options);

    expect(options.body).toEqual({ query: "draw cards" });
    expect(fetch).toHaveBeenCalledWith("/api/search", expect.objectContaining({
      body: JSON.stringify(options.body),
      headers: { "Content-Type": "application/json" },
    }));
  });

  it("turns unsuccessful JSON responses into a typed error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: vi.fn().mockResolvedValue({ detail: "Too many searches" }),
    }));

    await expect(apiJson("/api/search")).rejects.toEqual(
      expect.objectContaining({
        name: "ApiError",
        message: "Too many searches",
        status: 429,
      }),
    );
    await apiJson("/api/search").catch((error) => expect(error).toBeInstanceOf(ApiError));
  });
});
