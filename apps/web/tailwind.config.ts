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

        /* ── Light marketing theme (constructor.com-style). Used only inside
              the .theme-light marketing shell; the dark app tokens above are
              untouched so the dashboard keeps its dark look. ── */
        mkt: {
          bg:        "#ffffff",   // page
          surface:   "#f8fafc",   // subtle section background
          elevated:  "#f1f5f9",   // cards on surface
          border:    "#e2e8f0",   // hairlines
          ink:       "#0f172a",   // primary text (near-black navy)
          body:      "#475569",   // body text
          muted:     "#94a3b8",   // muted text
          brand:     "#4f46e5",   // primary indigo
          "brand-d": "#4338ca",   // darker hover
          teal:      "#0d9488",   // constructor-style teal accent
          "teal-l":  "#14b8a6",
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
        marquee: {
          "0%":   { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
      },
      animation: {
        "fade-up":    "fadeUp 0.4s ease-out forwards",
        "slide-in":   "slideIn 0.3s ease-out forwards",
        "blink":      "blink 0.85s ease-in-out infinite",
        "shimmer":    "shimmer 2.2s linear infinite",
        "pulse-slow": "pulse 3s cubic-bezier(0.4,0,0.6,1) infinite",
        "marquee":    "marquee 32s linear infinite",
        "marquee-slow": "marquee 55s linear infinite",
      },
      backgroundImage: {
        "shimmer-gradient":
          "linear-gradient(90deg, transparent 25%, rgba(255,255,255,0.04) 50%, transparent 75%)",
        "grid-glow":
          "radial-gradient(circle at 50% 0%, rgba(99,102,241,0.15) 0%, transparent 55%)",
        "hero-grid":
          "linear-gradient(rgba(99,102,241,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.06) 1px, transparent 1px)",
      },
      maxWidth: {
        "8xl": "88rem",
      },
    },
  },
  plugins: [],
};

export default config;
