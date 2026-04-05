import adapter from '@sveltejs/adapter-static';
import { relative, sep } from 'node:path';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	compilerOptions: {
		runes: ({ filename }) => {
			const relativePath = relative(import.meta.dirname, filename);
			const pathSegments = relativePath.toLowerCase().split(sep);
			const isExternalLibrary = pathSegments.includes('node_modules');
			return isExternalLibrary ? undefined : true;
		}
	},
	kit: {
		// adapter-static: compila a HTML/JS/CSS estático servible por Caddy
		adapter: adapter({
			fallback: 'index.html'  // SPA mode: todas las rutas usan index.html
		})
	}
};

export default config;
