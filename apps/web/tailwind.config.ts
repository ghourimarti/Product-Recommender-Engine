import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          base:     "#05050a",
          surface:  "#0f0f1a",
          elevated: "#16162a",
          border:   "#1e1e3a",
        },
        accent: {
          DEFAULT: "#6366f1",
          hover:   "#818cf8",
          muted:   "rgba(99,102,241,0.12)",
        },
        rank: {
          gold:   "#f59e0b",
          silver: "#94a3b8",
          bronze: "#cd7c2f",
        },
        status: {
          success: "#10b981",
          warning: "#f59e0b",
          error:   "#ef4444",
          info:    "#3b82f6",
        },
        txt: {
          primary:   "#f1f5f9",
          secondary: "#94a3b8",
          muted:     "#64748b",
        },
      },
      fontFamily: {
        sans:    ["var(--font-inter)", "system-ui", "sans-serif"],
        display: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono:    ["var(--font-mono)", "monospace"],
      },
      keyframes: {
        fadeUp: {
          "0%":   { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        slideIn: {
          "0%":   { opacity: "0", transform: "translateX(16px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%":      { opacity: "0" },
        },
        shimmer: {
          "0%":   { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      animation: {
        "fade-up":    "fadeUp 0.4s ease-out forwards",
        "slide-in":   "slideIn 0.3s ease-out forwards",
        "blink":      "blink 0.85s ease-in-out infinite",
        "shimmer":    "shimmer 2.2s linear infinite",
        "pulse-slow": "pulse 3s cubic-bezier(0.4,0,0.6,1) infinite",
      },
      backgroundImage: {
        "shimmer-gradient":
          "linear-gradient(90deg, transparent 25%, rgba(255,255,255,0.04) 50%, transparent 75%)",
      },
    },
  },
  plugins: [],
};

export default config;
