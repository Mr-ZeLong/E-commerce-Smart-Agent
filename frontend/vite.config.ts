import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    rollupOptions: {
      input: {
        customer: path.resolve(__dirname, 'index.html'),
        admin: path.resolve(__dirname, 'admin.html'),
      },
      output: {
        dir: 'dist',
        entryFileNames: (chunkInfo) => {
          const name = chunkInfo.name
          if (name === 'customer' || name === 'admin') {
            return '[name]/assets/[name]-[hash].js'
          }
          return 'shared/[name]-[hash].js'
        },
        chunkFileNames: 'shared/[name]-[hash].js',
        assetFileNames: (assetInfo) => {
          const info = assetInfo.name || ''
          if (/\.css$/.test(info)) {
            const chunkName = assetInfo.name?.replace('.css', '') || 'chunk'
            if (chunkName === 'customer' || chunkName === 'admin') {
              return '[name]/assets/[name]-[hash][extname]'
            }
          }
          return 'assets/[name]-[hash][extname]'
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
