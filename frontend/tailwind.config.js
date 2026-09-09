/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Neutral matte black. No blue cast, no gloss - the greys step evenly
        // so panels read as depth rather than as colour.
        marine: {
          950: '#0c0c0d',
          900: '#111112',
          850: '#161617',
          800: '#1c1c1e',
          750: '#232326',
          700: '#2b2b2f',
        },
        ink: '#0a0a0b',
        panel: '#141416',
        'panel-light': '#1b1b1d',
        line: '#26262a',
        'line-bright': '#343439',
        muted: '#8a8a91',

        // One accent, cool and low-saturation - the colour of an instrument
        // face, not a highlighter. It marks what is interactive or current;
        // everything else stays grey, which is what stops a dark UI turning
        // into a light show.
        wreck: '#6d8bab',
        'wreck-dim': '#48607a',

        // Status colours, desaturated to sit on black without glowing.
        ghost: '#b5645f',
        hazard: '#b8904a',
        safe: '#6f9270',
        intel: '#7b7f96',
      },
    },
  },
  plugins: [],
}
