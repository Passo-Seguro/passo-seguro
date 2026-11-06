import { defineConfig, minimal2023Preset } from '@vite-pwa/assets-generator/config';

// Gera os ícones do PWA a partir de public/favicon.svg:  npm run gen:icones
export default defineConfig({
  preset: {
    ...minimal2023Preset,
    maskable: { sizes: [512], padding: 0.2, resizeOptions: { background: '#ffc93c', fit: 'contain' } },
    apple: { sizes: [180], padding: 0.15, resizeOptions: { background: '#ffc93c', fit: 'contain' } },
  },
  images: ['public/favicon.svg'],
});
