import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { usePersistentDisclosure } from "./usePersistentDisclosure";

describe("usePersistentDisclosure", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("restores a section state after its component is remounted", () => {
    const firstRender = renderHook(() =>
      usePersistentDisclosure("test-section", true),
    );

    act(() => {
      firstRender.result.current[1](false);
    });
    firstRender.unmount();

    const secondRender = renderHook(() =>
      usePersistentDisclosure("test-section", true),
    );

    expect(secondRender.result.current[0]).toBe(false);
  });

  it("stores each section independently", () => {
    const firstSection = renderHook(() =>
      usePersistentDisclosure("first-section", true),
    );
    const secondSection = renderHook(() =>
      usePersistentDisclosure("second-section", true),
    );

    act(() => {
      firstSection.result.current[1](false);
    });

    expect(firstSection.result.current[0]).toBe(false);
    expect(secondSection.result.current[0]).toBe(true);
  });
});
