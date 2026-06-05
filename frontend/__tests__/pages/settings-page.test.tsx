import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SettingsPage from "@/app/(platform)/settings/page";

vi.mock("@/lib/config", () => ({
  API_BASE_URL: "http://localhost:8001/api/v1",
  secureFetch: vi.fn(),
}));

import { secureFetch } from "@/lib/config";

const mockSecureFetch = vi.mocked(secureFetch);

function mockFetchResponse(data: unknown, ok = true) {
  return Promise.resolve({
    ok,
    json: () => Promise.resolve(data),
  } as Response);
}

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSecureFetch.mockImplementation(() => mockFetchResponse({}));
  });

  it("shows loading state initially", () => {
    mockSecureFetch.mockImplementation(() => new Promise(() => {}));
    render(<SettingsPage />);
    expect(screen.getByText("Retrieving system configurations...")).toBeInTheDocument();
  });

  it("renders page title after loading", async () => {
    render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByText("Runtime Settings")).toBeInTheDocument();
    });
  });

  it("renders save and reset buttons", async () => {
    render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByLabelText("Save settings")).toBeInTheDocument();
      expect(screen.getByLabelText("Reset to defaults")).toBeInTheDocument();
    });
  });

  it("renders LM Studio Connection section", async () => {
    render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByText("LM Studio Connection")).toBeInTheDocument();
    });
  });

  it("renders TurboQuant KV Cache section", async () => {
    render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByText("TurboQuant KV Cache")).toBeInTheDocument();
    });
  });

  it("renders VRAM Pressure Monitor section", async () => {
    render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByText("VRAM Pressure Monitor")).toBeInTheDocument();
    });
  });

  it("renders System Portals section", async () => {
    render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByText("System Portals")).toBeInTheDocument();
    });
  });

  it("populates config fields from API response", async () => {
    mockSecureFetch.mockImplementation(() =>
      mockFetchResponse({
        llm_host: "http://192.168.1.100",
        llm_port: 8080,
        llm_model: "Qwen3-8B",
      })
    );
    render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByText("Runtime Settings")).toBeInTheDocument();
    });
    const modelInput = screen.getAllByLabelText("Model Identifier")[0] as HTMLInputElement;
    expect(modelInput.value).toBe("Qwen3-8B");
  });

  it("toggle switch renders with correct initial state", async () => {
    render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByText("Runtime Settings")).toBeInTheDocument();
    });
    const toggle = screen.getByRole("switch", { name: /Quantization Enabled/i });
    expect(toggle).toHaveAttribute("aria-checked", "true");
  });

  it("save button triggers PUT request", async () => {
    render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.queryByText("Retrieving system configurations...")).not.toBeInTheDocument();
    });
    const saveBtn = screen.getByLabelText("Save settings");
    fireEvent.click(saveBtn);
    await waitFor(() => {
      expect(mockSecureFetch).toHaveBeenCalledWith(
        "http://localhost:8001/api/v1/config",
        expect.objectContaining({ method: "PUT" })
      );
    });
  });

  it("shows success toast after save", async () => {
    render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.queryByText("Retrieving system configurations...")).not.toBeInTheDocument();
    });
    fireEvent.click(screen.getByLabelText("Save settings"));
    await waitFor(() => {
      expect(screen.getByText(/Successfully saved/)).toBeInTheDocument();
    });
  });
});
