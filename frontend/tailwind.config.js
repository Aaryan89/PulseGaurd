/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        pg: {
          bg: '#0F1419',      // Void Slate
          surface: '#1A2027', // Instrument Gray
          border: '#2D3748',  // Hard border
          text: '#E2E8F0',    // Crisp Silver
          muted: '#94A3B8',
          cyan: '#38BDF8',    // Terminal Cyan
          amber: '#F5A623',   // Review/Caution
          crimson: '#E11D48', // Breach Crimson
        }
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      }
    },
  },
  plugins: [],
}
