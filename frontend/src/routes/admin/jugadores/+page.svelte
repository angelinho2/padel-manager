<script>
	import { onMount } from 'svelte';
	import { jugadores as jugadoresApi } from '$lib/api.js';
	import { goto } from '$app/navigation';

	let lista     = $state([]);
	let loading   = $state(true);
	let buscar    = $state('');
	let soloActivos = $state(true);
	let showForm  = $state(false);
	let nuevo     = $state({ nombre: '', nivel: 3, telefono: '' });
	let guardando = $state(false);
	let toast     = $state(null);

	onMount(cargar);

	async function cargar() {
		loading = true;
		try {
			const params = soloActivos ? { activo: 'true' } : {};
			if (buscar.trim()) params.buscar = buscar.trim();
			lista = await jugadoresApi.listar(params);
		} catch (e) { showToast(e.message, false); }
		finally { loading = false; }
	}

	async function crear(e) {
		e.preventDefault();
		guardando = true;
		try {
			await jugadoresApi.crear({ ...nuevo, telefono: nuevo.telefono || null });
			showForm = false;
			nuevo = { nombre: '', nivel: 3, telefono: '' };
			await cargar();
			showToast('Jugador creado');
		} catch (e) { showToast(e.message, false); }
		finally { guardando = false; }
	}

	function showToast(msg, ok = true) {
		toast = { msg, ok };
		setTimeout(() => toast = null, 2200);
	}

	let debounceTimer;
	function onBuscar() {
		clearTimeout(debounceTimer);
		debounceTimer = setTimeout(cargar, 300);
	}
</script>

<svelte:head><title>Jugadores — Padel Manager</title></svelte:head>

{#if toast}
<div class="toast-container">
	<div class="toast" class:toast-ok={toast.ok} class:toast-err={!toast.ok}>{toast.msg}</div>
</div>
{/if}

<div class="page">
	<div class="page-header">
		<h1>👤 Jugadores</h1>
		<button class="btn btn-primary btn-sm" onclick={() => showForm = !showForm}>
			{showForm ? 'Cancelar' : '＋ Nuevo'}
		</button>
	</div>

	<!-- Formulario nuevo jugador -->
	{#if showForm}
	<div class="card" style="margin-bottom:1rem">
		<form onsubmit={crear} style="display:flex;flex-direction:column;gap:.75rem">
			<div class="field">
				<label for="nombre">Nombre completo</label>
				<input id="nombre" type="text" bind:value={nuevo.nombre} placeholder="Ej: García, Pedro" required />
			</div>
			<div class="field">
				<label for="nivel">Nivel (1=mejor, 6=peor)</label>
				<select id="nivel" bind:value={nuevo.nivel}>
					{#each [1,2,3,4,5,6] as n}
					<option value={n}>Nivel {n} — Pista {n}</option>
					{/each}
				</select>
			</div>
			<div class="field">
				<label for="tel">Teléfono (opcional)</label>
				<input id="tel" type="tel" bind:value={nuevo.telefono} placeholder="+34 600 000 000" />
			</div>
			<button class="btn btn-primary" type="submit" disabled={guardando}>
				{guardando ? 'Guardando…' : 'Crear jugador'}
			</button>
		</form>
	</div>
	{/if}

	<!-- Búsqueda y filtros -->
	<div style="display:flex;gap:.5rem;margin-bottom:1rem;align-items:center">
		<div class="field" style="flex:1;margin:0">
			<input
				type="search"
				placeholder="🔍 Buscar jugador…"
				bind:value={buscar}
				oninput={onBuscar}
				style="padding:.55rem .9rem"
			/>
		</div>
		<label style="display:flex;align-items:center;gap:.3rem;white-space:nowrap;font-size:.85rem;color:var(--text-1)">
			<input type="checkbox" bind:checked={soloActivos} onchange={cargar} />
			Solo activos
		</label>
	</div>

	<!-- Lista -->
	{#if loading} <div class="spinner"></div>
	{:else if lista.length === 0}
	<div class="empty">
		<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
			<circle cx="9" cy="7" r="4"/><path d="M3 21v-2a4 4 0 014-4h4a4 4 0 014 4v2"/>
		</svg>
		<p>Sin jugadores. {buscar ? 'Prueba otra búsqueda.' : 'Crea el primero.'}</p>
	</div>
	{:else}
	<div style="display:flex;flex-direction:column;gap:.5rem">
		{#each lista as j}
		<a href="/admin/jugadores/{j.id}" class="card jugador-row">
			<div class="flex items-center gap-sm">
				<span class="pista-chip pista-{j.nivel}">{j.nivel}</span>
				<div style="flex:1">
					<div style="font-weight:600">{j.nombre}</div>
					{#if j.telefono}<div class="text-muted" style="font-size:.8rem">{j.telefono}</div>{/if}
				</div>
				{#if !j.activo}<span class="badge badge-red">Inactivo</span>{/if}
			</div>
		</a>
		{/each}
	</div>
	{/if}
</div>

<style>
.jugador-row {
	display: block; text-decoration: none; color: inherit;
	transition: border-color .15s, transform .1s;
}
.jugador-row:hover  { border-color: var(--accent); transform: translateY(-1px); }
.jugador-row:active { transform: scale(.98); }
</style>
