import { describe, expect, it } from "vitest";
import { formatDuration, formatTimestamp, parseVideoRef, timeAgo, ANALYSIS_LABEL } from "./utils";

describe("utils", () => {
  it("formats durations", () => {
    expect(formatDuration(0)).toBe("–");
    expect(formatDuration(75)).toBe("1:15");
    expect(formatDuration(3723)).toBe("1:02:03");
    expect(formatTimestamp(null)).toBe("");
    expect(formatTimestamp(0)).toBe("0:00");
  });
  it("parses video refs and rejects look-alike hosts", () => {
    expect(parseVideoRef("https://youtu.be/dQw4w9WgXcQ?si=1")).toBe("dQw4w9WgXcQ");
    expect(parseVideoRef("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=5")).toBe("dQw4w9WgXcQ");
    expect(parseVideoRef("https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ")).toBeNull();
    expect(parseVideoRef("https://www.youtube.com/watch?v=short")).toBeNull();
    expect(parseVideoRef("dQw4w9WgXcQ")).toBe("dQw4w9WgXcQ");
  });
  it("time ago", () => {
    const now = Date.parse("2026-01-02T00:00:00Z");
    expect(timeAgo(null)).toBe("never");
    expect(timeAgo("2026-01-01T23:59:30Z", now)).toBe("just now");
    expect(timeAgo("2026-01-01T22:00:00Z", now)).toBe("2 h ago");
  });
  it("never labels missing sources as analyzed", () => {
    expect(ANALYSIS_LABEL.source_required.text).toBe("Source required");
    expect(ANALYSIS_LABEL.blocked.tone).toBe("red");
  });
});
