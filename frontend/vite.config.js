import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import svgr from 'vite-plugin-svgr';

// 2026-03-12: Migrated from react-scripts (EOL) to Vite
// 2026-05-10: Added vite-plugin-svgr so SVGs imported with ?react render as React components.
// Used for Material Symbols icon imports — see frontend/src/icons.js.
export default defineConfig({
  plugins: [
    react({
      // Include .js files for JSX transform (CRA convention)
      include: '**/*.{js,jsx}',
    }),
    svgr({
      include: '**/*.svg?react',
      svgrOptions: {
        // Make all paths inherit color from CSS — lets us style with `color: …`
        svgProps: { fill: 'currentColor' },
      },
    }),
  ],
  server: {
    port: 2026,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'https://localhost:8443',
        secure: false,
      },
    },
  },
  build: {
    outDir: 'build',
  },
});
