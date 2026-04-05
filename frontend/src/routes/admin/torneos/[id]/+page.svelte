<script>
	import { onMount } from 'svelte';
	import { torneos, inscripciones, jugadores as jugadoresApi } from '$lib/api.js';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	const torneoId = $derived(Number($page.params.id));

	let torneo         = $state(null);
	let confirmados    = $state([]);
	let espera         = $state([]);
	let todosJugadores = $state([]);
	let loading        = $state(true);
	let error          = $state('');
	let toast          = $state(null);
	let showApuntar    = $state(false);
	let apuntarSearch  = $state('');
	let guardando      = $state(false);

	// Registro rápido
	let showNuevoJugador = $state(false);
	let nuevoJugador     = $state({ nombre: '', nivel: 4, telefono: '' });
	let guardandoNuevo   = $state(false);

	const ESTADOS = {
		abierto:    { label: 'Abierto',    cls: 'badge-green' },
		cerrado:    { label: 'Cerrado',    cls: 'badge-amber' },
		en_curso:   { label: 'En curso',   cls: 'badge-blue'  },
		finalizado: { label: 'Finalizado', cls: 'badge-red'   },
	};

	// Todos los estados excepto el actual — para cambiar libremente
	const TODOS_ESTADOS = ['abierto', 'cerrado', 'en_curso', 'finalizado'];

	onMount(cargar);

	async function cargar() {
		loading = true;
		try {
			const [datos, jug] = await Promise.all([
				torneos.obtener(torneoId),
				jugadoresApi.listar(),
			]);
			torneo         = datos.torneo;
			confirmados    = datos.confirmados;
			espera         = datos.espera;
			todosJugadores = jug;
		} catch (e) { error = e.message; }
		finally { loading = false; }
	}

	function showToast(msg, ok = true) {
		toast = { msg, ok };
		setTimeout(() => toast = null, 2500);
	}

	async function cambiarEstado(nuevoEstado) {
		try {
			await torneos.estado(torneoId, nuevoEstado);
			torneo.estado = nuevoEstado;
			showToast(`Estado: ${ESTADOS[nuevoEstado]?.label}`);
		} catch (e) { showToast(e.message, false); }
	}

	// ── Inscribir jugador existente ───────────────────────────────
	async function apuntar(e) {
		e.preventDefault();
		guardando = true;
		try {
			// El datalist produce "15 - Juan Pérez" - sacamos el id del prefijo
			const parts = apuntarSearch.split(' - ');
			const id = Number(parts[0].trim());
			if (!id || isNaN(id)) throw new Error('Selecciona un jugador válido de la lista');

			const res = await inscripciones.apuntar(torneoId, { jugador_id: id });
			showToast(res.mensaje);
			apuntarSearch = '';
			showApuntar   = false;
			await cargar();
		} catch (e) { showToast(e.message, false); }
		finally { guardando = false; }
	}

	// ── Crear jugador y apuntar en un paso ────────────────────────
	async function crearYApuntar(e) {
		e.preventDefault();
		guardandoNuevo = true;
		try {
			const j = await jugadoresApi.crear({
				nombre: nuevoJugador.nombre,
				nivel:  Number(nuevoJugador.nivel),
				telefono: nuevoJugador.telefono || null,
			});
			const res = await inscripciones.apuntar(torneoId, { jugador_id: j.id });
			showToast(`✅ ${j.nombre} registrado y apuntado`);
			showNuevoJugador = false;
			showApuntar      = false;
			nuevoJugador     = { nombre: '', nivel: 4, telefono: '' };
			await cargar();
		} catch (e) { showToast(e.message, false); }
		finally { guardandoNuevo = false; }
	}

	async function darBaja(inscripcionId) {
		try {
			const res = await inscripciones.baja(inscripcionId);
			showToast(res.mensaje);
			await cargar();
		} catch (e) { showToast(e.message, false); }
	}

	function irPistas() { goto(`/admin/pistas?torneo=${torneoId}`); }
	function irCobros() { goto(`/admin/cobros?torneo=${torneoId}`); }
</script>

<svelte:head><title>Torneo — Padel Manager</title></svelte:head>

{#if toast}
<div class="toast-container">
	<div class="toast" class:toast-ok={toast.ok} class:toast-err={!toast.ok}>{toast.msg}</div>
</div>
{/if}

<div class="page">
	<div class="page-header">
		<a href="/admin/torneos" class="btn btn-ghost btn-sm">← Volver</a>
		<h1 style="flex:1;margin:0">Torneo</h1>
	</div>

	{#if loading} <div class="spinner"></div>
	{:else if error} <div class="error-block">{error}</div>
	{:else if torneo}

	<!-- Info del torneo -->
	<div class="card" style="margin-bottom:1rem">
		<div class="flex items-center justify-between" style="margin-bottom:.75rem">
			<div>
				<div style="font-weight:700;font-size:1.1rem">
					{new Date(torneo.fecha + 'T12:00').toLocaleDateString('es-ES', { weekday:'long', day:'numeric', month:'long' })}
				</div>
				<div class="text-muted">Precio: {torneo.precio_base}€</div>
			</div>
			<span class="badge {ESTADOS[torneo.estado]?.cls}">{ESTADOS[torneo.estado]?.label}</span>
		</div>

		<!-- Cambio de estado — TODOS los estados visibles siempre -->
		<div class="estado-btns">
			{#each TODOS_ESTADOS as est}
			<button
				class="btn btn-sm estado-btn"
				class:estado-activo={torneo.estado === est}
				class:btn-ghost={torneo.estado !== est}
				onclick={() => cambiarEstado(est)}
				disabled={torneo.estado === est}
			>{ESTADOS[est]?.label}</button>
			{/each}
		</div>

		<!-- Acciones -->
		<div style="display:flex;gap:.5rem;margin-top:.75rem;flex-wrap:wrap">
			<button class="btn btn-ghost btn-sm" onclick={irPistas}>🎾 Pistas</button>
			<button class="btn btn-ghost btn-sm" onclick={irCobros}>💰 Cobros</button>
		</div>
	</div>

	<!-- Resumen -->
	<div class="resumen-grid" style="margin-bottom:1rem">
		<div class="resumen-item">
			<div class="resumen-num">{confirmados.length}<span>/24</span></div>
			<div class="resumen-label">Confirmados</div>
		</div>
		<div class="resumen-item">
			<div class="resumen-num" style="color:var(--green)">{confirmados.filter(c => c.pagado).length}</div>
			<div class="resumen-label">Pagados</div>
		</div>
		<div class="resumen-item">
			<div class="resumen-num" style="color:var(--amber)">{espera.length}</div>
			<div class="resumen-label">En espera</div>
		</div>
	</div>

	<!-- Apuntar jugador -->
	<div class="flex items-center justify-between" style="margin-bottom:.5rem">
		<h2>Confirmados ({confirmados.length}/24)</h2>
		<button class="btn btn-ghost btn-sm" onclick={() => { showApuntar = !showApuntar; showNuevoJugador = false; }}>
			{showApuntar ? 'Cancelar' : '＋ Apuntar'}
		</button>
	</div>

	{#if showApuntar}
	<div class="card" style="margin-bottom:1rem">

		<!-- Buscador por nombre -->
		<form onsubmit={apuntar} style="display:flex;gap:.5rem;margin-bottom:.75rem">
			<div class="field" style="flex:1">
				<label for="jsearch">Buscar jugador</label>
				<input
					id="jsearch"
					type="text"
					list="players-dl"
					bind:value={apuntarSearch}
					placeholder="Escribe el nombre…"
					autocomplete="off"
					required
				/>
				<datalist id="players-dl">
					{#each todosJugadores as j}
					<option value="{j.id} - {j.nombre} (N{j.nivel})"></option>
					{/each}
				</datalist>
			</div>
			<button class="btn btn-primary" type="submit" style="align-self:flex-end" disabled={guardando}>
				{guardando ? '…' : 'Apuntar'}
			</button>
		</form>

		<!-- Separador + opción de crear nuevo -->
		<div style="border-top:1px solid var(--bg-3);padding-top:.75rem">
			<button
				class="btn btn-ghost btn-sm"
				style="width:100%;justify-content:center"
				onclick={() => showNuevoJugador = !showNuevoJugador}
			>
				{showNuevoJugador ? '✕ Cancelar registro' : '＋ Registrar jugador nuevo'}
			</button>

			{#if showNuevoJugador}
			<form onsubmit={crearYApuntar} style="display:flex;flex-direction:column;gap:.65rem;margin-top:.75rem;background:var(--bg-0);padding:.75rem;border-radius:var(--radius-sm)">
				<div class="field">
					<label for="nn_nombre">Nombre completo *</label>
					<input id="nn_nombre" type="text" bind:value={nuevoJugador.nombre} required placeholder="Nombre Apellido" />
				</div>
				<div style="display:flex;gap:.5rem">
					<div class="field" style="flex:1">
						<label for="nn_nivel">Nivel (1-6)</label>
						<input id="nn_nivel" type="number" bind:value={nuevoJugador.nivel} min="1" max="6" step="1" required />
					</div>
					<div class="field" style="flex:1">
						<label for="nn_tel">Teléfono</label>
						<input id="nn_tel" type="tel" bind:value={nuevoJugador.telefono} placeholder="Opcional" />
					</div>
				</div>
				<button type="submit" class="btn btn-primary" disabled={guardandoNuevo}>
					{guardandoNuevo ? 'Guardando…' : '✅ Crear y Apuntar'}
				</button>
			</form>
			{/if}
		</div>
	</div>
	{/if}

	<!-- Lista confirmados -->
	<div style="display:flex;flex-direction:column;gap:.5rem;margin-bottom:1.5rem">
		{#each confirmados as c}
		<div class="card jugador-row">
			<div class="flex items-center justify-between">
				<div>
					<span class="pista-chip pista-{c.jugador.nivel}">{c.jugador.nivel}</span>
					<span style="font-weight:600;margin-left:.5rem">{c.jugador.nombre}</span>
					{#if c.pista_asignada}
					<span class="badge badge-accent" style="margin-left:.4rem">Pista {c.pista_asignada}</span>
					{/if}
					{#if c.pagado}
					<span class="badge badge-green" style="margin-left:.4rem">✓</span>
					{/if}
				</div>
				<button class="btn btn-danger btn-sm" onclick={() => darBaja(c.inscripcion_id)}>Baja</button>
			</div>
		</div>
		{/each}
	</div>

	<!-- Lista de espera -->
	{#if espera.length > 0}
	<h2 style="margin-bottom:.5rem">En espera</h2>
	<div style="display:flex;flex-direction:column;gap:.5rem">
		{#each espera as e}
		<div class="card jugador-row" style="opacity:.75">
			<div class="flex items-center gap-sm">
				<span class="text-muted" style="min-width:1.5rem">#{e.inscripcion?.posicion_espera ?? e.posicion_espera}</span>
				<span class="pista-chip pista-{e.jugador.nivel}">{e.jugador.nivel}</span>
				<span style="font-weight:500">{e.jugador.nombre}</span>
			</div>
		</div>
		{/each}
	</div>
	{/if}

	{/if}
</div>

<style>
.resumen-grid {
	display: grid; grid-template-columns: repeat(3, 1fr); gap: .75rem;
}
.resumen-item {
	background: var(--bg-2); border: 1px solid var(--bg-3); border-radius: var(--radius);
	padding: .75rem; text-align: center;
}
.resumen-num { font-size: 1.75rem; font-weight: 800; line-height: 1; }
.resumen-num span { font-size: 1rem; color: var(--text-2); font-weight: 400; }
.resumen-label { font-size: .75rem; color: var(--text-2); margin-top: .25rem; }
.jugador-row { padding: .65rem .9rem; }

/* Estado buttons */
.estado-btns {
	display: flex; gap: .4rem; flex-wrap: wrap;
}
.estado-btn {
	flex: 1; min-width: 80px; text-align: center; font-size: .78rem;
	border: 1px solid var(--bg-3);
}
.estado-activo {
	border-color: var(--accent) !important;
	color: var(--accent) !important;
	opacity: 1 !important;
}
</style>
