import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#070D1A",
          900: "#0A1020",
          850: "#0D1526",
          800: "#111A2E",
          750: "#15203A",
          700: "#1A2742",
          600: "#24365A",
          500: "#31466F",
        },
        mist: {
          100: "#E6ECF7",
          200: "#C7D3E8",
          300: "#A7B6D3",
          400: "#8A9AB8",
          500: "#6D7E9E",
        },
        brand: {
          400: "#7B96FF",
          500: "#5B7CFA",
          600: "#4966E0",
          700: "#3B53BD",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "PingFang SC",
          "Microsoft YaHei",
          "Noto Sans SC",
          "sans-serif",
        ],
      },
      boxShadow: {
        card: "0 18px 50px -30px rgba(0,0,0,0.9)",
        glow: "0 0 0 1px rgba(91,124,250,0.25), 0 20px 60px -30px rgba(91,124,250,0.45)",
      },
    },
  },
  plugins: [],
} satisfies Config;
