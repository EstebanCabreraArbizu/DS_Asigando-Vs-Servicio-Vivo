/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./dashboard/templates/**/*.html",
        "./dashboard/static/**/*.js",
        "./api_v1/templates/**/*.html",
        "./jobs/templates/**/*.html",
    ],
    theme: {
        extend: {
            colors: {
                'neon-red': '#ff133f',
                'neon-red-strong': '#ff2a57',
                'neon-cyan': '#00cfdc',
                'neon-cyan-soft': 'rgba(0, 207, 220, 0.34)',
                'neon-amber': '#f8d57c',
            },
            fontFamily: {
                display: ['Orbitron', 'Tourney', 'system-ui', 'sans-serif'],
                body: ['Rajdhani', 'system-ui', 'sans-serif'],
                mono: ['Syne Mono', 'monospace'],
            },
        },
    },
    plugins: [],
}
