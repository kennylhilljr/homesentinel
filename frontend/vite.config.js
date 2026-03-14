import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// 2026-03-12: Migrated from react-scripts (EOL) to Vite
export default defineConfig({
  plugins: [
    react({
      // Include .js files for JSX transform (CRA convention)
      include: '**/*.{js,jsx}',
    }),
  ],
  server: {
    port: 3000,
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
