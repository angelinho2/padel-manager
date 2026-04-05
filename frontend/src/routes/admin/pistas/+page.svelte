<script>
	/**
	 * Página de pistas — la pantalla clave de la Fase 2.
	 *
	 * Flujo:
	 *  1. El admin elige el torneo activo (viene por query param o lo selecciona)
	 *  2. Pulsa "Generar" → algoritmo automático asigna pistas
	 *  3. Puede arrastrar jugadores entre pistas para ajustar (drag & drop)
	 *  4. Pulsa "Guardar" para persistir los cambios
	 *  5. Pulsa "Publicar" para que los jugadores vean su pista
	 */
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { pistas as pistasApi, torneos as torneosApi } from '$lib/api.js';

	// Obtenemos el torneo de la URL (?torneo=X) o permitimos seleccionarlo
	let torneoId   = $state(Number($page.url.searchParams.get('torneo')) || null);
	let listaTorneos = $state([]);
	let pistasData = $state({});   // { "1": [...jugadores], "2": [...], ... }
	let publicadas = $state(false);
	let loading    = $state(false);
	let toast      = $state(null);

	// Drag & Drop state
	let dragging       = $state(null);  // { jugador, fromPista }
	let dragOverPista  = $state(null);

	onMount(async () => {
		listaTorneos = await torneosApi.listar();
		if (torneoId) await cargarPistas();
	});

	async function cargarPistas() {
		if (!torneoId) return;
		loading = true;
		try {
			const res = await pistasApi.ver(torneoId);
			// Convertir claves a números
			pistasData = Object.fromEntries(
				Object.entries(res.pistas).map(([k, v]) => [Number(k), v])
			);
			publicadas = res.publicadas;
		} catch (e) { showToast(e.message, false); }
		finally { loading = false; }
	}

	async function generar() {
		loading = true;
		try {
			const res = await pistasApi.generar(torneoId);
			pistasData = Object.fromEntries(
				Object.entries(res.pistas).map(([k, v]) => [Number(k), v])
			);
			publicadas = false;
			showToast('¡Pistas generadas! Ajusta si necesitas y publica.');
		} catch (e) { showToast(e.message, false); }
		finally { loading = false; }
	}

	async function guardar() {
		loading = true;
		try {
			// Convertir de { pista: [{jugador_id, ...}] } a { pista: [jugador_id, ...] }
			const payload = Object.fromEntries(
				Object.entries(pistasData).map(([k, jugadores]) => [k, jugadores.map(j => j.jugador_id)])
			);
			await pistasApi.guardar(torneoId, payload);
			showToast('Asignación guardada');
		} catch (e) { showToast(e.message, false); }
		finally { loading = false; }
	}

	async function publicar() {
		loading = true;
		try {
			await pistasApi.publicar(torneoId);
			publicadas = true;
			showToast('¡Pistas publicadas! Los jugadores ya pueden verlas 🎾');
		} catch (e) { showToast(e.message, false); }
		finally { loading = false; }
	}

	function showToast(msg, ok = true) {
		toast = { msg, ok };
		setTimeout(() => toast = null, 3000);
	}

	// ── Drag & Drop ─────────────────────────────────────────────

	function onDragStart(jugador, fromPista) {
		dragging = { jugador, fromPista };
	}

	function onDragOver(e, pistaNum) {
		e.preventDefault();
		dragOverPista = pistaNum;
	}

	function onDragLeave() {
		dragOverPista = null;
	}

	function onDrop(e, toPista) {
		e.preventDefault();
		dragOverPista = null;
		if (!dragging || dragging.fromPista === toPista) { dragging = null; return; }

		const { jugador, fromPista } = dragging;
		dragging = null;

		// Quitar de la pista origen
		pistasData[fromPista] = pistasData[fromPista].filter(j => j.jugador_id !== jugador.jugador_id);

		// Añadir a la pista destino
		pistasData[toPista] = [...(pistasData[toPista] || []), jugador];

		// Reasignar pista al jugador en memoria
		jugador.pista_asignada = toPista;

		// Forzar reactividad de Svelte
		pistasData = { ...pistasData };
	}

	// Touch drag (móvil) — simpler swap on tap
	let selectedJugador = $state(null);

	function onTap(jugador, fromPista) {
		if (!selectedJugador) {
			selectedJugador = { jugador, fromPista };
			return;
		}
		// Segundo tap: si es la misma pista, deseleccionar
		if (selectedJugador.jugador.jugador_id === jugador.jugador_id) {
			selectedJugador = null;
			return;
		}
		// Intercambio entre jugadores (puede ser misma pista o diferentes)
		const a = selectedJugador;
		const b = { jugador, fromPista };
		swap(a, b);
		selectedJugador = null;
	}

	function swap(a, b) {
		// Eliminar ambos de sus pistas
		pistasData[a.fromPista] = pistasData[a.fromPista].filter(j => j.jugador_id !== a.jugador.jugador_id);
		pistasData[b.fromPista] = pistasData[b.fromPista].filter(j => j.jugador_id !== b.jugador.jugador_id);

		// Cruzar: a va a la pista de b y viceversa
		pistasData[b.fromPista] = [...pistasData[b.fromPista], a.jugador];
		pistasData[a.fromPista] = [...pistasData[a.fromPista], b.jugador];

		a.jugador.pista_asignada = b.fromPista;
		b.jugador.pista_asignada = a.fromPista;

		pistasData = { ...pistasData };
	}

	const hasPistas = $derived(Object.keys(pistasData).length > 0);
	const pistaNums = $derived(
		hasPistas ? [1,2,3,4,5,6].filter(n => pistasData[n]) : []
	);
</script>

<svelte:head><title>Pistas — Padel Manager</title></svelte:head>

{#if toast}
<div class="toast-container">
	<div class="toast" class:toast-ok={toast.ok} class:toast-err={!toast.ok}>{toast.msg}</div>
</div>
{/if}

<div class="page">
	<div class="page-header" style="justify-content:flex-start;gap:.75rem">
		<a href={torneoId ? `/admin/torneos/${torneoId}` : '/admin/torneos'} class="btn btn-ghost btn-sm">← Volver</a>
		<h1 style="flex:1;margin:0">🎾 Pistas</h1>
		{#if publicadas}<span class="badge badge-green">Publicadas</span>{/if}
	</div>

	<!-- Selector de torneo -->
	<div class="card" style="margin-bottom:1rem">
		<div class="field">
			<label for="torneo-sel">Torneo</label>
			<select id="torneo-sel" bind:value={torneoId} onchange={cargarPistas}>
				<option value={null}>— Selecciona un torneo —</option>
				{#each listaTorneos as t}
				<option value={t.id}>
					{new Date(t.fecha + 'T12:00').toLocaleDateString('es-ES', { weekday:'short', day:'numeric', month:'short' })}
					— {t.estado}
				</option>
				{/each}
			</select>
		</div>

		{#if torneoId}
		<div style="display:flex;gap:.5rem;margin-top:.75rem;flex-wrap:wrap">
			<button class="btn btn-primary btn-sm" onclick={generar} disabled={loading}>
				{loading ? '…' : '⚡ Generar pistas'}
			</button>
			{#if hasPistas}
			<button class="btn btn-ghost btn-sm" onclick={guardar} disabled={loading}>💾 Guardar</button>
			{#if !publicadas}
			<button class="btn btn-ghost btn-sm" onclick={publicar} disabled={loading} style="color:var(--accent)">
				🌐 Publicar
			</button>
			{/if}
			{/if}
		</div>
		{/if}
	</div>

	<!-- Instrucción -->
	{#if hasPistas && !publicadas}
	<p class="text-muted text-sm" style="margin-bottom:1rem">
		💡 <strong>En móvil:</strong> toca un jugador y luego otro para intercambiarlos.<br>
		   <strong>En ordenador:</strong> arrastra y suelta entre pistas. Guarda cuando estés listo.
	</p>
	{/if}

	{#if loading && !hasPistas}
	<div class="spinner"></div>
	{:else if !torneoId}
	<div class="empty">
		<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
			<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
			<rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
		</svg>
		<p>Selecciona un torneo para gestionar las pistas.</p>
	</div>
	{:else if !hasPistas}
	<div class="empty">
		<p>Sin asignación aún. Pulsa <strong>⚡ Generar pistas</strong> para empezar.</p>
	</div>
	{:else}

	<!-- Grid de pistas -->
	<div class="pistas-grid">
		{#each pistaNums as pistaNum}
		{@const jugadores = pistasData[pistaNum] || []}
		<div
			class="pista-col drop-zone"
			class:drag-over={dragOverPista === pistaNum}
			ondragover={(e) => onDragOver(e, pistaNum)}
			ondragleave={onDragLeave}
			ondrop={(e) => onDrop(e, pistaNum)}
			role="region"
			aria-label="Pista {pistaNum}"
		>
			<!-- Header de pista -->
			<div class="pista-header pista-{pistaNum}">
				<span class="pista-num">Pista {pistaNum}</span>
				<span class="pista-count">{jugadores.length}/4</span>
			</div>

			<!-- Jugadores en esta pista -->
			<div class="pista-jugadores">
				{#each jugadores as j}
				{@const isSelected = selectedJugador?.jugador.jugador_id === j.jugador_id}
				<div
					class="drag-item jugador-card pista-{pistaNum}"
					class:selected={isSelected}
					draggable={!publicadas}
					ondragstart={() => onDragStart(j, pistaNum)}
					onclick={() => !publicadas && onTap(j, pistaNum)}
					role="button"
					tabindex="0"
					aria-label="{j.nombre} - Nivel {j.nivel}"
					onkeydown={(e) => e.key === 'Enter' && !publicadas && onTap(j, pistaNum)}
				>
					<span class="jugador-nivel">N{j.nivel}</span>
					<span class="jugador-nombre">{j.nombre}</span>
					{#if j.acompanante_id}
					<span class="acomp-icon" title="Tiene acompañante">👥</span>
					{/if}
				</div>
				{/each}

				{#if jugadores.length < 4}
				<div class="drop-placeholder">
					Arrastra aquí ({4 - jugadores.length} hueco{4 - jugadores.length !== 1 ? 's' : ''})
				</div>
				{/if}
			</div>
		</div>
		{/each}
	</div>

	<!-- Botones flotantes en móvil -->
	{#if !publicadas}
	<div class="fab-row">
		<button class="btn btn-ghost" onclick={guardar} disabled={loading}>💾 Guardar cambios</button>
		<button class="btn btn-primary" onclick={publicar} disabled={loading}>🌐 Publicar</button>
	</div>
	{/if}

	{/if}
</div>

<style>
/* ── Pistas Grid ─────────────────────────────────────────── */
.pistas-grid {
	display: flex;
	flex-direction: column;
	gap: .75rem;
	padding-bottom: 5rem; /* espacio para FAB */
}

/* En tablet+: 2 columnas */
@media (min-width: 480px) {
	.pistas-grid { display: grid; grid-template-columns: repeat(2, 1fr); }
}
@media (min-width: 900px) {
	.pistas-grid { grid-template-columns: repeat(3, 1fr); }
}

.pista-col {
	background: var(--bg-2);
	border: 2px solid var(--bg-3);
	border-radius: var(--radius);
	overflow: hidden;
	transition: border-color .15s, background .15s;
}
.pista-col.drag-over {
	border-color: var(--accent);
	background: var(--accent-glow);
}

/* Header con color por pista */
.pista-header {
	display: flex; align-items: center; justify-content: space-between;
	padding: .55rem .9rem;
	font-weight: 700; font-size: .9rem;
}
.pista-1.pista-header { background: rgba(168,85,247,.2);  color: var(--p1); }
.pista-2.pista-header { background: rgba(59,130,246,.2);  color: var(--p2); }
.pista-3.pista-header { background: rgba(34,211,238,.2);  color: var(--p3); }
.pista-4.pista-header { background: rgba(34,197,94,.2);   color: var(--p4); }
.pista-5.pista-header { background: rgba(251,146,60,.2);  color: var(--p5); }
.pista-6.pista-header { background: rgba(244,63,94,.2);   color: var(--p6); }

.pista-num  { font-weight: 800; }
.pista-count{ font-size: .75rem; opacity: .7; }

.pista-jugadores {
	padding: .5rem;
	display: flex; flex-direction: column; gap: .4rem;
	min-height: 180px;
}

/* Tarjeta de jugador con borde de color de su pista */
.jugador-card {
	display: flex; align-items: center; gap: .5rem;
	background: var(--bg-0); border-radius: var(--radius-sm);
	padding: .5rem .65rem;
	font-size: .85rem; font-weight: 500;
	border-left: 3px solid transparent;
	transition: all .12s;
	user-select: none;
}
.jugador-card:hover { filter: brightness(1.2); }
.jugador-card.selected {
	border-left-color: var(--accent);
	box-shadow: 0 0 0 2px var(--accent-glow);
}

.pista-1 .jugador-card { border-left-color: var(--p1); }
.pista-2 .jugador-card { border-left-color: var(--p2); }
.pista-3 .jugador-card { border-left-color: var(--p3); }
.pista-4 .jugador-card { border-left-color: var(--p4); }
.pista-5 .jugador-card { border-left-color: var(--p5); }
.pista-6 .jugador-card { border-left-color: var(--p6); }

/* Workaround: el color del borde viene del contenedor, no del jugador */
.pistas-grid .pista-col:nth-child(1) .jugador-card { border-left-color: var(--p1); }
.pistas-grid .pista-col:nth-child(2) .jugador-card { border-left-color: var(--p2); }
.pistas-grid .pista-col:nth-child(3) .jugador-card { border-left-color: var(--p3); }
.pistas-grid .pista-col:nth-child(4) .jugador-card { border-left-color: var(--p4); }
.pistas-grid .pista-col:nth-child(5) .jugador-card { border-left-color: var(--p5); }
.pistas-grid .pista-col:nth-child(6) .jugador-card { border-left-color: var(--p6); }

.jugador-nivel {
	font-size: .7rem; font-weight: 700;
	background: var(--bg-3); border-radius: 4px;
	padding: .1rem .3rem; color: var(--text-1);
}
.jugador-nombre { flex: 1; }
.acomp-icon { font-size: .75rem; }

.drop-placeholder {
	text-align: center; font-size: .75rem; color: var(--text-2);
	padding: .75rem; border: 1px dashed var(--bg-3); border-radius: var(--radius-sm);
	flex: 1;
}

/* FAB row — botones flotantes en la parte inferior */
.fab-row {
	position: fixed; bottom: calc(var(--nav-h) + .75rem);
	left: .75rem; right: .75rem;
	display: flex; gap: .5rem;
	z-index: 50;
}
.fab-row .btn { flex: 1; box-shadow: var(--shadow-lg); }

@media (min-width: 640px) {
	.fab-row { bottom: .75rem; }
}
</style>
