<script>
	import { goto } from '$app/navigation';
	import { login } from '$lib/api.js';
	import { onMount } from 'svelte';
	import { isLoggedIn } from '$lib/api.js';

	let username = $state('admin');
	let password = $state('');
	let loading  = $state(false);
	let error    = $state('');

	onMount(() => {
		if (isLoggedIn()) goto('/admin/torneos');
	});

	async function handleLogin(e) {
		e.preventDefault();
		loading = true;
		error   = '';
		try {
			await login(username, password);
			goto('/admin/torneos');
		} catch (err) {
			error = err.message;
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head><title>Acceder — Padel Manager</title></svelte:head>

<div class="login-page">
	<div class="login-card">
		<div class="logo">
			<svg viewBox="0 0 48 48" fill="none">
				<circle cx="24" cy="24" r="22" fill="rgba(34,211,165,.15)" stroke="rgba(34,211,165,.4)" stroke-width="1.5"/>
				<ellipse cx="24" cy="24" rx="11" ry="14" stroke="#22d3a5" stroke-width="2.5"/>
				<line x1="16" y1="14" x2="32" y2="34" stroke="#22d3a5" stroke-width="2" stroke-linecap="round"/>
				<line x1="14" y1="18" x2="34" y2="30" stroke="#22d3a5" stroke-width="1.5" stroke-linecap="round" opacity=".5"/>
			</svg>
		</div>

		<h1>Padel Manager</h1>
		<p class="subtitle">Panel de administración</p>

		<form onsubmit={handleLogin}>
			<div class="field">
				<label for="username">Usuario</label>
				<input id="username" type="text" bind:value={username} autocomplete="username" required />
			</div>
			<div class="field">
				<label for="password">Contraseña</label>
				<input id="password" type="password" bind:value={password} autocomplete="current-password" required />
			</div>

			{#if error}
			<div class="error-block">{error}</div>
			{/if}

			<button class="btn btn-primary w-full" type="submit" disabled={loading}>
				{loading ? 'Accediendo…' : 'Acceder'}
			</button>
		</form>
	</div>
</div>

<style>
.login-page {
	min-height: 100dvh;
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 1.5rem;
	background: radial-gradient(ellipse at 60% 0%, rgba(34,211,165,.08) 0%, transparent 60%);
}
.login-card {
	width: 100%;
	max-width: 360px;
	display: flex;
	flex-direction: column;
	gap: 1.25rem;
}
.logo {
	width: 64px; height: 64px;
	margin: 0 auto;
}
.logo svg { width: 100%; height: 100%; }
h1 { text-align: center; font-size: 1.8rem; }
.subtitle { text-align: center; font-size: .9rem; }
form { display: flex; flex-direction: column; gap: 1rem; margin-top: .5rem; }
</style>
