export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { 50:'#f0f9ff', 100:'#e0f2fe', 500:'#0ea5e9', 600:'#0284c7', 700:'#0369a1', 900:'#0c4a6e' },
        danger: { 50:'#fef2f2', 500:'#ef4444', 700:'#b91c1c' },
        success: { 50:'#f0fdf4', 500:'#22c55e', 700:'#15803d' },
        warning: { 50:'#fffbeb', 500:'#f59e0b', 700:'#b45309' },
      }
    }
  },
  plugins: []
}
