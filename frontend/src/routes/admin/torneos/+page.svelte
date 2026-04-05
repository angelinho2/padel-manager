<script>
	import { onMount } from 'svelte';
	import { torneos } from '$lib/api.js';
	import { goto } from '$app/navigation';

	let lista     = $state([]);
	let loading   = $state(true);
	let error     = $state('');
	let toast     = $state(null);
	let showForm  = $state(false);
	let nueva     = $state({ fecha: '', precio_base: 10 });
	let guardando = $state(false);
	let eliminando = $state(null);  // ID del torneo en proceso de eliminación

	function showToast(msg, ok = true) {
		toast = { msg, ok };
		setTimeout(() => toast = null, 2500);
	}

	const ESTADOS = {
		abierto:    { label: 'Abierto',    cls: 'badge-green'  },
		cerrado:    { label: 'Cerrado',    cls: 'badge-amber'  },
		en_curso:   { label: 'En curso',   cls: 'badge-blue'   },
		finalizado: { label: 'Finalizado', cls: 'badge-red'    }
	};

	onMount(async () => {
		await cargar();
	});

	async function cargar() {
		loading = true;
		try {
			lista = await torneos.listar();
		} catch (e) {
			error = e.message;
		} finally {
			loading = false;
		}
	}

	async function crear(e) {
		e.preventDefault();
		guardando = true;
		try {
			await torneos.crear(nueva);
			showForm = false;
			nueva = { fecha: '', precio_base: 10 };
			await cargar();
		} catch (e) {
			error = e.message;
		} finally {
			guardando = false;
		}
	}

	function abrirTorneo(id) {
		goto(`/admin/torneos/${id}`);
	}

	async function eliminarTorneo(e, id) {
		e.stopPropagation(); // no abrir el torneo
		if (!confirm('¿Eliminar este torneo y todas sus inscripciones? Esta acción no se puede deshacer.')) return;
		eliminando = id;
		try {
			await torneos.eliminar(id);
			showToast('Torneo eliminado');
			await cargar();
		} catch (e) {
			showToast(e.message || 'Error al eliminar', false);
		} finally {
			eliminando = null;
		}
	}
</script>

<svelte:head><title>Torneos — Padel Manager</title></svelte:head>

{#if toast}
<div class="toast-container">
	<div class="toast" class:toast-ok={toast.ok} class:toast-err={!toast.ok}>{toast.msg}</div>
</div>
{/if}

<div class="page">
	<div class="page-header">
		<h1>🏆 Torneos</h1>
		<button class="btn btn-primary btn-sm" onclick={() => showForm = !showForm}>
			{showForm ? 'Cancelar' : '＋ Nuevo'}
		</button>
	</div>

	{#if showForm}
	<div class="card" style="margin-bottom:1rem">
		<form onsubmit={crear} style="display:flex;flex-direction:column;gap:.75rem">
			<div class="field">
				<label for="fecha">Fecha (sábado)</label>
				<input id="fecha" type="date" bind:value={nueva.fecha} required />
			</div>
			<div class="field">
				<label for="precio">Precio base (€)</label>
				<input id="precio" type="number" step="0.01" bind:value={nueva.precio_base} />
			</div>
			<button class="btn btn-primary" type="submit" disabled={guardando}>
				{guardando ? 'Creando…' : 'Crear torneo'}
			</button>
		</form>
	</div>
	{/if}

	{#if error}   <div class="error-block">{error}</div>{/if}
	{#if loading} <div class="spinner"></div>
	{:else if lista.length === 0}
	<div class="empty">
		<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
			<path d="M8 21h8M12 17v4M5 3H3v5c0 2.2 1.8 4 4 4m12-9h2v5c0 2.2-1.8 4-4 4M5 3h14v6c0 3.3-2.7 6-6 6h-2c-3.3 0-6-2.7-6-6V3z"/>
		</svg>
		<p>Sin torneos aún. Crea el primero.</p>
	</div>
	{:else}
	<div style="display:flex;flex-direction:column;gap:.75rem">
		{#each lista as t}
		<div class="torneo-row">
			<button class="card torneo-card" onclick={() => abrirTorneo(t.id)}>
				<div class="flex items-center justify-between">
					<div>
						<div class="torneo-fecha">{new Date(t.fecha + 'T12:00').toLocaleDateString('es-ES', { weekday:'long', day:'numeric', month:'long' })}</div>
						<div class="text-muted" style="margin-top:.2rem">Precio: {t.precio_base}€</div>
					</div>
					<span class="badge {ESTADOS[t.estado]?.cls}">{ESTADOS[t.estado]?.label}</span>
				</div>
			</button>
			<button
				class="btn-eliminar"
				onclick={(e) => eliminarTorneo(e, t.id)}
				disabled={eliminando === t.id}
				aria-label="Eliminar torneo"
				title="Eliminar torneo"
			>{eliminando === t.id ? '…' : '🗑️'}</button>
		</div>
		{/each}
	</div>
	{/if}
</div>

<style>
.torneo-row {
	display: flex;
	align-items: stretch;
	gap: .5rem;
}
.torneo-card {
	flex: 1;
	text-align: left;
	cursor: pointer;
	transition: border-color .15s, transform .1s;
	background: none;
	color: inherit;
	font-family: inherit;
}
.torneo-card:hover  { border-color: var(--accent); transform: translateY(-1px); }
.torneo-card:active { transform: scale(.98); }
.torneo-fecha { font-weight: 600; font-size: 1rem; text-transform: capitalize; }

.btn-eliminar {
	width: 44px;
	border: 1px solid var(--bg-3);
	border-radius: var(--radius);
	background: var(--bg-2);
	color: var(--text-2);
	font-size: 1.1rem;
	cursor: pointer;
	transition: all .15s;
	padding: 0;
	flex-shrink: 0;
}
.btn-eliminar:hover    { background: rgba(248,113,113,.15); border-color: rgba(248,113,113,.4); color: var(--red); }
.btn-eliminar:disabled { opacity: .4; cursor: not-allowed; }
</style>
