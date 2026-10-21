import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/** Configure React compilation and the local backend proxy. */
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
