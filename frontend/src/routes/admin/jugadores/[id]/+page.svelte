<script>
	import { onMount } from 'svelte';
	import { jugadores as jugadoresApi } from '$lib/api.js';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	const jugadorId = $derived(Number($page.params.id));

	let jugador   = $state(null);
	let historial = $state([]);
	let loading   = $state(true);
	let error     = $state('');
	let toast     = $state(null);

	// Edición
	let editando  = $state(false);
	let form      = $state({ nombre: '', nivel: 1, telefono: '' });
	let guardando = $state(false);

	const ESTADOS_INS = {
		confirmado: { label: 'Confirmado', cls: 'badge-green'  },
		espera:     { label: 'Espera',     cls: 'badge-amber'  },
		baja:       { label: 'Baja',       cls: 'badge-red'    },
	};

	onMount(cargar);

	async function cargar() {
		loading = true;
		try {
			const datos = await jugadoresApi.historial(jugadorId);
			jugador  = datos.jugador;
			historial = datos.historial;
			form = {
				nombre:   jugador.nombre,
				nivel:    jugador.nivel,
				telefono: jugador.telefono ?? '',
			};
		} catch (e) { error = e.message; }
		finally { loading = false; }
	}

	function showToast(msg, ok = true) {
		toast = { msg, ok };
		setTimeout(() => toast = null, 2500);
	}

	async function guardarEdicion(e) {
		e.preventDefault();
		guardando = true;
		try {
			await jugadoresApi.actualizar(jugadorId, {
				nombre:   form.nombre,
				nivel:    Number(form.nivel),
				telefono: form.telefono || null,
			});
			showToast('Datos guardados');
			editando = false;
			await cargar();
		} catch (e) { showToast(e.message, false); }
		finally { guardando = false; }
	}

	async function desactivar() {
		if (!confirm(`¿Marcar a ${jugador.nombre} como inactivo? Conservará su historial pero no aparecerá en las listas activas.`)) return;
		try {
			await jugadoresApi.eliminar(jugadorId);
			showToast('Jugador marcado como inactivo');
			goto('/admin/jugadores');
		} catch (e) { showToast(e.message, false); }
	}

	async function reactivar() {
		try {
			await jugadoresApi.actualizar(jugadorId, { activo: true });
			showToast('Jugador reactivado');
			await cargar();
		} catch (e) { showToast(e.message, false); }
	}

	// Stats rápidas
	const totalConfirmados = $derived(historial.filter(h => h.estado === 'confirmado').length);
	const totalPagados     = $derived(historial.filter(h => h.pagado).length);
</script>

<svelte:head><title>{jugador?.nombre ?? 'Jugador'} — Padel Manager</title></svelte:head>

{#if toast}
<div class="toast-container">
	<div class="toast" class:toast-ok={toast.ok} class:toast-err={!toast.ok}>{toast.msg}</div>
</div>
{/if}

<div class="page">
	<div class="page-header">
		<a href="/admin/jugadores" class="btn btn-ghost btn-sm">← Volver</a>
		<h1 style="flex:1;margin:0">{jugador?.nombre ?? '…'}</h1>
		{#if jugador && !jugador.activo}
		<span class="badge badge-red">Inactivo</span>
		{/if}
	</div>

	{#if loading} <div class="spinner"></div>
	{:else if error} <div class="error-block">{error}</div>
	{:else if jugador}

	<!-- Stats rápidas -->
	<div class="stats-row" style="margin-bottom:1rem">
		<div class="stat-card">
			<span class="stat-num pista-chip pista-{jugador.nivel}" style="width:2.2rem;height:2.2rem;font-size:1.1rem;display:flex;align-items:center;justify-content:center">{jugador.nivel}</span>
			<span class="stat-label">Nivel</span>
		</div>
		<div class="stat-card">
			<span class="stat-num">{totalConfirmados}</span>
			<span class="stat-label">Torneos</span>
		</div>
		<div class="stat-card">
			<span class="stat-num" style="color:var(--green)">{totalPagados}</span>
			<span class="stat-label">Pagados</span>
		</div>
		{#if jugador.telefono}
		<div class="stat-card" style="grid-column:span 3">
			<a href="tel:{jugador.telefono}" style="font-size:.9rem;color:var(--accent)">📞 {jugador.telefono}</a>
		</div>
		{/if}
	</div>

	<!-- Datos / edición -->
	<div class="card" style="margin-bottom:1rem">
		{#if !editando}
		<div style="display:flex;align-items:center;justify-content:space-between">
			<div>
				<div style="font-weight:600;margin-bottom:.2rem">{jugador.nombre}</div>
				<div class="text-muted text-sm">Nivel {jugador.nivel} — {jugador.activo ? 'Activo' : 'Inactivo'}</div>
				{#if jugador.telefono}<div class="text-muted text-sm">📞 {jugador.telefono}</div>{/if}
				<div class="text-muted text-sm" style="margin-top:.25rem">Alta: {new Date(jugador.created_at).toLocaleDateString('es-ES')}</div>
			</div>
			<div style="display:flex;flex-direction:column;gap:.4rem;align-items:flex-end">
				<button class="btn btn-ghost btn-sm" onclick={() => editando = true}>✏️ Editar</button>
				{#if jugador.activo}
				<button class="btn btn-danger btn-sm" onclick={desactivar}>Desactivar</button>
				{:else}
				<button class="btn btn-ghost btn-sm" style="color:var(--green)" onclick={reactivar}>✅ Reactivar</button>
				{/if}
			</div>
		</div>

		{:else}
		<!-- Formulario edición -->
		<form onsubmit={guardarEdicion} style="display:flex;flex-direction:column;gap:.65rem">
			<div class="field">
				<label for="ed_nombre">Nombre completo</label>
				<input id="ed_nombre" type="text" bind:value={form.nombre} required />
			</div>
			<div style="display:flex;gap:.5rem">
				<div class="field" style="flex:1">
					<label for="ed_nivel">Nivel (1-6)</label>
					<select id="ed_nivel" bind:value={form.nivel}>
						{#each [1,2,3,4,5,6] as n}
						<option value={n}>Nivel {n}</option>
						{/each}
					</select>
				</div>
				<div class="field" style="flex:1">
					<label for="ed_tel">Teléfono</label>
					<input id="ed_tel" type="tel" bind:value={form.telefono} placeholder="Opcional" />
				</div>
			</div>
			<div style="display:flex;gap:.5rem">
				<button type="submit" class="btn btn-primary" style="flex:1" disabled={guardando}>
					{guardando ? 'Guardando…' : '💾 Guardar'}
				</button>
				<button type="button" class="btn btn-ghost" onclick={() => editando = false}>Cancelar</button>
			</div>
		</form>
		{/if}
	</div>

	<!-- Historial -->
	<h2 style="margin-bottom:.5rem">Historial de torneos</h2>

	{#if historial.length === 0}
	<div class="empty">
		<p>Sin torneos registrados.</p>
	</div>
	{:else}
	<div style="display:flex;flex-direction:column;gap:.5rem;padding-bottom:2rem">
		{#each historial as h}
		<a href="/admin/torneos/{h.torneo.id}" class="card historial-row">
			<div class="historial-fecha">
				{new Date(h.torneo.fecha + 'T12:00').toLocaleDateString('es-ES', { weekday:'short', day:'numeric', month:'short', year:'numeric' })}
			</div>
			<div class="historial-badges">
				<span class="badge {ESTADOS_INS[h.estado]?.cls ?? ''}">{ESTADOS_INS[h.estado]?.label ?? h.estado}</span>
				{#if h.pista_asignada}
				<span class="badge badge-accent">Pista {h.pista_asignada}</span>
				{/if}
				{#if h.pagado}
				<span class="badge badge-green">✓ Pagado</span>
				{:else if h.estado === 'confirmado'}
				<span class="badge badge-red">Pendiente pago</span>
				{/if}
			</div>
		</a>
		{/each}
	</div>
	{/if}

	{/if}
</div>

<style>
.stats-row {
	display: grid; grid-template-columns: repeat(3, 1fr); gap: .6rem;
}
.stat-card {
	background: var(--bg-2); border: 1px solid var(--bg-3); border-radius: var(--radius);
	padding: .65rem; display: flex; flex-direction: column; align-items: center; gap: .2rem; text-align: center;
}
.stat-num  { font-size: 1.5rem; font-weight: 800; line-height: 1; }
.stat-label { font-size: .7rem; color: var(--text-2); }

.historial-row {
	display: flex; align-items: center; justify-content: space-between;
	text-decoration: none; color: inherit; gap: .5rem; flex-wrap: wrap;
	transition: border-color .15s;
}
.historial-row:hover { border-color: var(--accent); }
.historial-fecha { font-weight: 600; font-size: .9rem; text-transform: capitalize; }
.historial-badges { display: flex; gap: .3rem; flex-wrap: wrap; }
</style>
