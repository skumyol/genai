import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    watch: {
      // Exclude database files and other backend files from being watched
      ignored: [
        '**/backend/databases/**',
        '**/backend/**/*.db',
        '**/backend/**/*.db-shm',
        '**/backend/**/*.db-wal',
        '**/backend/**/*.log',
        '**/logs/**',
        '**/metrics/**',
        '**/.venv/**',
        '**/node_modules/**'
      ]
    }
  }
})
