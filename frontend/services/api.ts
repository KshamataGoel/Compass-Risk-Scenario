import type { CommentaryResponse, ConfigOptions, SimulationResult } from "@/lib/types";

// All calls go to the FastAPI backend via the /api proxy (next.config.js rewrite).
// The frontend never talks to Groq directly; commentary is generated server-side.

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  async health(): Promise<{ status: string; groq_configured: boolean; model: string }> {
    return j(await fetch("/api/health"));
  },

  async dataHealth(): Promise<any> {
    return j(await fetch("/api/data-health"));
  },

  async configOptions(): Promise<ConfigOptions> {
    return j(await fetch("/api/config/options"));
  },

  async runSimulation(body: {
    portfolio_type: string;
    forward_horizon_days: number;
    lookback_days: number;
    confidence_level: number;
    dimensions: string[];
  }): Promise<SimulationResult> {
    return j(
      await fetch("/api/simulation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
    );
  },

  async commentary(simulationResult: SimulationResult): Promise<CommentaryResponse> {
    return j(
      await fetch("/api/commentary", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ simulation_result: simulationResult }),
      })
    );
  },

  async route(text: string): Promise<import("@/lib/types").RiskStripeClassification> {
    return j(
      await fetch("/api/route", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      })
    );
  },

  async operationalResilience(text: string): Promise<import("@/lib/types").ORResult> {
    return j(
      await fetch("/api/operational-resilience", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      })
    );
  },

  async orCommentary(orResult: import("@/lib/types").ORResult): Promise<CommentaryResponse> {
    return j(
      await fetch("/api/or-commentary", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ or_result: orResult }),
      })
    );
  },

  async parseParameters(text: string, current: Record<string, any>): Promise<{
    parsed: Record<string, any> | null;
    resolved: {
      portfolio_type: string;
      risk_horizon_days: number;
      historical_pnl_lookback: number;
      confidence_level: number;
      commentary_dimensions: string[];
      interpretation: string;
    };
    interpretation: string;
    source: "groq" | "fallback";
    note: string | null;
  }> {
    return j(
      await fetch("/api/parse-parameters", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, current }),
      })
    );
  },

  async saveSimulation(simulationResult: SimulationResult): Promise<{
    saved: boolean;
    run_id?: string;
    saved_at?: string;
    path?: string;
    simulation_var?: number;
    runs_in_file?: number;
    message?: string;
  }> {
    return j(
      await fetch("/api/save-simulation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ simulation_result: simulationResult }),
      })
    );
  },
};
