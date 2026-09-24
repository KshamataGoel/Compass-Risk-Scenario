import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#0b1220",
          muted: "#5b6472",
        },
        panel: "#ffffff",
        canvas: "#f4f6fa",
        accent: "#0f4c81",
        positive: "#0f7b57",
        negative: "#b42318",
        warn: "#b45309",
        line: "#e4e8ef",
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "Segoe UI", "Arial", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
