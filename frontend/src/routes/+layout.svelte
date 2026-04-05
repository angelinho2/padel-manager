<script>
	import '../app.css';
	import { page } from '$app/stores';
	import { isLoggedIn, logout } from '$lib/api.js';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';

	let { children } = $props();

	// Rutas que NO requieren autenticación
	const PUBLIC = ['/login'];

	onMount(() => {
		if (!PUBLIC.includes($page.url.pathname) && !isLoggedIn()) {
			goto('/login');
		}
	});

	const navItems = [
		{ href: '/admin/torneos',  label: 'Torneos',   icon: 'trophy'   },
		{ href: '/admin/pistas',   label: 'Pistas',    icon: 'grid'     },
		{ href: '/admin/cobros',   label: 'Cobros',    icon: 'money'    },
		{ href: '/admin/jugadores',label: 'Jugadores', icon: 'people'   },
	];

	function isActive(href) {
		return $page.url.pathname.startsWith(href);
	}
</script>

{@render children()}

{#if isLoggedIn() && !PUBLIC.includes($page.url.pathname)}
<nav class="bottom-nav">
	{#each navItems as item}
	<a href={item.href} class="nav-item" class:active={isActive(item.href)}>
		{#if item.icon === 'trophy'}
		<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
			<path d="M8 21h8M12 17v4M5 3H3v5c0 2.2 1.8 4 4 4m12-9h2v5c0 2.2-1.8 4-4 4M5 3h14v6c0 3.3-2.7 6-6 6h-2c-3.3 0-6-2.7-6-6V3z"/>
		</svg>
		{/if}
		{#if item.icon === 'grid'}
		<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
			<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
			<rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
		</svg>
		{/if}
		{#if item.icon === 'money'}
		<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
			<circle cx="12" cy="12" r="9"/><path d="M12 6v1m0 10v1M9.5 9.5c0-1.1.9-2 2.5-2s2.5.9 2.5 2-1.1 2-2.5 2-2.5.9-2.5 2 .9 2 2.5 2 2.5-.9 2.5-2"/>
		</svg>
		{/if}
		{#if item.icon === 'people'}
		<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
			<circle cx="9" cy="7" r="4"/><path d="M3 21v-2a4 4 0 014-4h4a4 4 0 014 4v2"/>
			<path d="M16 3.13a4 4 0 010 7.75M21 21v-2a4 4 0 00-3-3.87"/>
		</svg>
		{/if}
		{item.label}
	</a>
	{/each}
</nav>
{/if}
