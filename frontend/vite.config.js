import { sveltekit } from '@sveltejs/kit/vite';
import { SvelteKitPWA } from '@vite-pwa/sveltekit';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit(),
		SvelteKitPWA({
			registerType: 'autoUpdate',
			manifest: {
				name: 'Padel Manager',
				short_name: 'Padel',
				description: 'Gestión de maratón de pádel',
				theme_color: '#0f172a',
				background_color: '#0f172a',
				display: 'standalone',
				orientation: 'portrait',
				start_url: '/',
				icons: [
					{ src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
					{ src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' }
				]
			},
			workbox: {
				// Cachear assets estáticos
				globPatterns: ['**/*.{js,css,html,ico,png,svg,webp}'],
				// Estrategia network-first para las peticiones API
				runtimeCaching: [
					{
						urlPattern: /^https?:\/\/.*\/api\//,
						handler: 'NetworkFirst',
						options: { cacheName: 'api-cache', networkTimeoutSeconds: 5 }
					}
				]
			}
		})
	],
	server: {
		proxy: {
			'/api': {
				target: 'http://localhost:8001',
				rewrite: (path) => path.replace(/^\/api/, '')
			},
			'/ws': {
				target: 'ws://localhost:8001',
				ws: true   // habilita proxy de WebSockets
			}
		}
	}
});
