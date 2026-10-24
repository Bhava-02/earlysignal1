import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'
import path from 'node:path'

// `npm run build`         -> dist/: the app for the EarlySignal server (api.py); it fetches the latest data at start-up
// `npm run build:single`  -> dist-single/index.html, ONE file with the data inside (works offline, any static host)
export default defineConfig(({ mode }) => ({
  plugins: [react(), ...(mode === 'single' ? [viteSingleFile()] : [])],
  base: './',
  json: { stringify: true },
  resolve: {
    alias: {
      '@bundle': mode === 'single' ? path.resolve(__dirname, '../data/processed/web/bundle_r1.json')
        : path.resolve(__dirname, 'src/lib/empty-bundle.json'),
    },
  },
  build: {
    outDir: mode === 'single' ? 'dist-single' : 'dist',
    chunkSizeWarningLimit: 6000,
  },
}))
