import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Genpact palette (matches RegComplianceApp).
        ink: {
          DEFAULT: "#181C23",
          muted: "#5b6472",
        },
        panel: "#ffffff",
        canvas: "#f5f5f5",
        accent: "#FFAD28",        // Genpact amber
        "accent-dark": "#e09820",
        positive: "#0f7b57",
        negative: "#b42318",
        warn: "#b45309",
        line: "#e8e8e8",
      },
      fontFamily: {
        sans: ["Segoe UI", "system-ui", "-apple-system", "Arial", "sans-serif"],
        display: ["Montserrat", "Segoe UI", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
