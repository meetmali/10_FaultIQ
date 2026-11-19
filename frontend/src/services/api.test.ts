import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, listFaultEvents, startAnalysis, uploadFile } from "./api";

function respond(status: number, body: unknown, contentType = "application/json") {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { "content-type": contentType } }),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("turns problem responses into ApiError with the stable code", async () => {
    vi.stubGlobal(
      "fetch",
      respond(415, { status: 415, code: "not_text", detail: "Not a CSV." }, "application/problem+json"),
    );
    const err = await uploadFile(new File(["x"], "a.csv"), "id", "lbnl_simulated").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("not_text");
    expect(err.message).toBe("Not a CSV.");
  });

  it("sends uploads as multipart form fields the API expects", async () => {
    const fetchMock = respond(201, { id: "u1" });
    vi.stubGlobal("fetch", fetchMock);
    await uploadFile(new File(["a,b"], "export.csv"), "eq-1", "lbnl_experimental");
    const [path, init] = fetchMock.mock.calls[0]!;
    expect(path).toBe("/api/v1/uploads");
    const form = init.body as FormData;
    expect(form.get("equipment_id")).toBe("eq-1");
    expect(form.get("format")).toBe("lbnl_experimental");
    expect((form.get("file") as File).name).toBe("export.csv");
  });

  it("posts snake_case JSON and builds query strings without empty values", async () => {
    const fetchMock = respond(202, { id: "a1", status: "queued" });
    vi.stubGlobal("fetch", fetchMock);
    await startAnalysis("u1", "basic");
    expect(JSON.parse(fetchMock.mock.calls[0]![1].body)).toEqual({ upload_id: "u1", point_set: "basic" });

    vi.stubGlobal("fetch", respond(200, { items: [], page: 1, page_size: 20, total: 0 }));
    await listFaultEvents({ kind: "fault", fault: undefined, page: 2 });
    expect(vi.mocked(fetch).mock.calls[0]![0]).toBe("/api/v1/fault-events?kind=fault&page=2");
  });
});
