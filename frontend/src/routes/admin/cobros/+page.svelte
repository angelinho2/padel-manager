<script>
	/**
	 * Pantalla de cobros — Fase 3
	 *
	 * Flujo:
	 * 1. El admin selecciona el torneo
	 * 2. Se carga el snapshot inicial (GET /torneos/{id}/cobros)
	 * 3. Se abre un WebSocket (/ws/torneos/{id}?token=xxx)
	 * 4. Cada vez que alguien toca "Pagar" o añade un extra,
	 *    el servidor notifica a TODOS los clientes conectados
	 *    → la pantalla se actualiza sin recargar
	 *
	 * Interacción móvil:
	 *  - Un toque en "Pagar" → toggle inmediato (optimistic update)
	 *  - Toque en el nombre → abre panel de extras
	 */
	import { onMount, onDestroy } from 'svelte';
	import { page } from '$app/stores';
	import { inscripciones as inscApi, torneos as torneosApi } from '$lib/api.js';

	let torneoId     = $state(Number($page.url.searchParams.get('torneo')) || null);
	let listaTorneos = $state([]);
	let datos        = $state(null);   // snapshot completo del servidor
	let loading      = $state(false);
	let toast        = $state(null);
	let extraModal   = $state(null);   // { inscripcion_id, nombre, extras }
	let nuevoExtra   = $state({ concepto: '', precio: 1.5 });
	let guardandoExtra = $state(false);

	// WebSocket
	let ws        = null;
	let wsStatus  = $state('desconectado');  // 'conectando' | 'ok' | 'error' | 'desconectado'
	let pingTimer = null;

	// ── Helpers ──────────────────────────────────────────────────

	function getToken() {
		return typeof localStorage !== 'undefined' ? localStorage.getItem('token') : '';
	}

	function getWsUrl(id) {
		const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
		return `${proto}//${window.location.host}/ws/torneos/${id}?token=${getToken()}`;
	}

	function showToast(msg, ok = true) {
		toast = { msg, ok };
		setTimeout(() => toast = null, 2500);
	}

	// ── WebSocket ─────────────────────────────────────────────────

	function conectarWS(id) {
		cerrarWS();
		wsStatus = 'conectando';
		ws = new WebSocket(getWsUrl(id));

		ws.onopen = () => {
			wsStatus = 'ok';
			// Ping cada 25s para mantener la conexión viva
			pingTimer = setInterval(() => ws?.readyState === 1 && ws.send('ping'), 25000);
		};

		ws.onmessage = (e) => {
			const msg = JSON.parse(e.data);
			if (msg.tipo === 'snapshot') {
				datos = msg;
				loading = false;
			}
		};

		ws.onerror = () => { wsStatus = 'error'; };
		ws.onclose = () => {
			wsStatus = 'desconectado';
			clearInterval(pingTimer);
			// Reconexión automática tras 3s si el componente sigue montado
			setTimeout(() => { if (torneoId) conectarWS(torneoId); }, 3000);
		};
	}

	function cerrarWS() {
		clearInterval(pingTimer);
		if (ws) { ws.onclose = null; ws.close(); ws = null; }
		wsStatus = 'desconectado';
	}

	// ── Carga inicial ─────────────────────────────────────────────

	onMount(async () => {
		listaTorneos = await torneosApi.listar();
		if (torneoId) await cargar(torneoId);
	});

	onDestroy(cerrarWS);

	async function cargar(id) {
		loading = true;
		datos = null;
		try {
			// 1. Snapshot REST para no esperar al WS
			const res = await fetch(`/api/torneos/${id}/cobros`, {
				headers: { Authorization: `Bearer ${getToken()}` }
			});
			if (res.ok) datos = await res.json();
		} catch {}
		loading = false;
		// 2. Abrir WS para actualizaciones en tiempo real
		conectarWS(id);
	}

	async function onTorneoChange() {
		if (torneoId) await cargar(torneoId);
		else cerrarWS();
	}

	// ── Acciones ──────────────────────────────────────────────────

	async function marcarPago(jug, metodo) {
		// Optimistic update
		const prevPagado  = jug.pagado;
		const prevMetodo  = jug.metodo_pago;
		// Toggle si mismo metodo, si no cambiar metodo
		if (jug.pagado && jug.metodo_pago === metodo) {
			jug.pagado     = false;
			jug.metodo_pago = null;
		} else {
			jug.pagado     = true;
			jug.metodo_pago = metodo;
		}
		datos = { ...datos };

		try {
			await fetch(`/api/inscripciones/${jug.inscripcion_id}/pago`, {
				method: 'PATCH',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${getToken()}`
				},
				body: JSON.stringify({ metodo })
			});
		} catch (e) {
			// Revertir si falla
			jug.pagado     = prevPagado;
			jug.metodo_pago = prevMetodo;
			datos = { ...datos };
			showToast('Error al guardar el pago', false);
		}
	}

	function abrirExtras(jug) {
		extraModal = { ...jug };
		nuevoExtra = { concepto: '', precio: 1.5 };
	}

	function cerrarExtras() { extraModal = null; }

	async function eliminarExtra(extraId) {
		try {
			await fetch(`/api/extras/${extraId}`, {
				method: 'DELETE',
				headers: { Authorization: `Bearer ${getToken()}` }
			});
			showToast('Extra eliminado');
			// El WS actualiza el modal automáticamente — cerramos para simplificar
			cerrarExtras();
		} catch { showToast('Error al eliminar', false); }
	}

	async function guardarExtra(e) {
		e.preventDefault();
		if (!extraModal) return;
		guardandoExtra = true;
		try {
			await fetch(`/api/inscripciones/${extraModal.inscripcion_id}/extras`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${getToken()}`
				},
				body: JSON.stringify(nuevoExtra)
			});
			showToast('Extra añadido');
			cerrarExtras();
		} catch { showToast('Error al añadir extra', false); }
		finally { guardandoExtra = false; }
	}

	// Ordenación — primero no pagados, luego por pista
	const jugadoresOrdenados = $derived(
		datos?.jugadores
			? [...datos.jugadores].sort((a, b) => {
				if (a.pagado !== b.pagado) return a.pagado ? 1 : -1;
				return (a.pista_asignada ?? 99) - (b.pista_asignada ?? 99);
			})
			: []
	);

	// Contadores recalculados desde el array — responden al optimistic update al instante
	const nPagados      = $derived(datos?.jugadores?.filter(j => j.pagado).length ?? 0);
	const nPendientes   = $derived((datos?.jugadores?.length ?? 0) - nPagados);
	const totalRecaudado = $derived(
		datos?.jugadores?.filter(j => j.pagado).reduce((s, j) => s + j.precio_total, 0) ?? 0
	);
	const totalEsperado  = $derived(
		datos?.jugadores?.reduce((s, j) => s + j.precio_total, 0) ?? 0
	);
	const recaudadoTarjeta  = $derived(
		datos?.jugadores?.filter(j => j.pagado && j.metodo_pago === 'tarjeta').reduce((s, j) => s + j.precio_total, 0) ?? 0
	);
	const recaudadoEfectivo = $derived(
		datos?.jugadores?.filter(j => j.pagado && j.metodo_pago === 'efectivo').reduce((s, j) => s + j.precio_total, 0) ?? 0
	);
	const pctPagado = $derived(
		datos?.jugadores?.length ? Math.round((nPagados / datos.jugadores.length) * 100) : 0
	);

	const wsColor = $derived(
		wsStatus === 'ok' ? '#22c55e' : wsStatus === 'conectando' ? '#fb923c' : '#f87171'
	);

	// ── Lista "semana que viene" — solo visual, no persiste ──
	let semanaQueViene = $state(new Set());  // Set de inscripcion_id
	let showSemanaPanel = $state(false);

	function toggleSemana(id) {
		const s = new Set(semanaQueViene);
		if (s.has(id)) s.delete(id); else s.add(id);
		semanaQueViene = s;
	}

	const listaSemana = $derived(
		datos?.jugadores?.filter(j => semanaQueViene.has(j.inscripcion_id)) ?? []
	);
</script>

<svelte:head><title>Cobros — Padel Manager</title></svelte:head>

<!-- Toast -->
{#if toast}
<div class="toast-container">
	<div class="toast" class:toast-ok={toast.ok} class:toast-err={!toast.ok}>{toast.msg}</div>
</div>
{/if}

<!-- Modal de extras -->
{#if extraModal}
<div class="modal-overlay" onclick={cerrarExtras} role="button" tabindex="-1" aria-label="Cerrar" onkeydown={(e)=>e.key==='Escape'&&cerrarExtras()}>
	<div class="modal" onclick={(e)=>e.stopPropagation()} role="dialog" aria-modal="true">
		<div class="modal-header">
			<h2>{extraModal.nombre}</h2>
			<button class="btn btn-ghost btn-sm" onclick={cerrarExtras}>✕</button>
		</div>

		<!-- Lista de extras actuales -->
		{#if extraModal.extras?.length > 0}
		<div class="extras-list">
			{#each extraModal.extras as ex}
			<div class="extra-row">
				<span class="extra-concepto">{ex.concepto}</span>
				<span class="extra-precio">{ex.precio.toFixed(2)} €</span>
				<button class="btn btn-danger btn-sm" onclick={() => eliminarExtra(ex.id)}>✕</button>
			</div>
			{/each}
			<div class="extra-total">
				Total extras: <strong>{extraModal.extras.reduce((s,e)=>s+e.precio,0).toFixed(2)} €</strong>
			</div>
		</div>
		{:else}
		<p class="text-muted" style="margin:.75rem 0">Sin extras.</p>
		{/if}

		<hr class="divider" />

		<!-- Añadir nuevo extra -->
		<form onsubmit={guardarExtra} style="display:flex;flex-direction:column;gap:.75rem">
			<h3>Añadir extra</h3>
			<div style="display:flex;gap:.5rem">
				<div class="field" style="flex:1">
					<label for="concepto">Concepto</label>
					<input id="concepto" type="text" bind:value={nuevoExtra.concepto}
						placeholder="Bebida, Snack…" required />
				</div>
				<div class="field" style="width:90px">
					<label for="precio-extra">€</label>
					<input id="precio-extra" type="number" step="0.01" min="0"
						bind:value={nuevoExtra.precio} required />
				</div>
			</div>
			<button class="btn btn-primary" type="submit" disabled={guardandoExtra}>
				{guardandoExtra ? 'Guardando…' : '＋ Añadir'}
			</button>
		</form>
	</div>
</div>
{/if}

<div class="page">
	<div class="page-header" style="justify-content:flex-start; gap:.75rem">
		<a href={torneoId ? `/admin/torneos/${torneoId}` : '/admin/torneos'} class="btn btn-ghost btn-sm">← Volver</a>
		<h1 style="flex:1; margin:0">💰 Cobros</h1>
		<!-- Indicador WS -->
		<div class="ws-dot" style="background:{wsColor}" title="WebSocket: {wsStatus}"></div>
	</div>

	<!-- Selector de torneo -->
	<div class="card" style="margin-bottom:1rem">
		<div class="field">
			<label for="torneo-sel">Torneo</label>
			<select id="torneo-sel" bind:value={torneoId} onchange={onTorneoChange}>
				<option value={null}>— Selecciona un torneo —</option>
				{#each listaTorneos as t}
				<option value={t.id}>
					{new Date(t.fecha + 'T12:00').toLocaleDateString('es-ES',
						{ weekday:'short', day:'numeric', month:'short' }
					)} — {t.estado}
				</option>
				{/each}
			</select>
		</div>
	</div>

	{#if loading}
	<div class="spinner"></div>

	{:else if datos}

	<!-- Barra de progreso de cobros -->
	<div class="cobros-stats">
		<div class="stats-row">
			<div class="stat">
				<span class="stat-num" style="color:var(--green)">{nPagados}</span>
				<span class="stat-label">Pagados</span>
			</div>
			<div class="stat">
				<span class="stat-num" style="color:var(--amber)">{nPendientes}</span>
				<span class="stat-label">Pendientes</span>
			</div>
			<div class="stat">
				<span class="stat-num" style="color:var(--accent)">{totalRecaudado.toFixed(0)}€</span>
				<span class="stat-label">Recaudado</span>
			</div>
			<div class="stat">
				<span class="stat-num" style="color:var(--text-2)">{totalEsperado.toFixed(0)}€</span>
				<span class="stat-label">Total</span>
			</div>
		</div>

		<!-- Desglose tarjeta / efectivo -->
		<div class="metodo-row">
			<div class="metodo-item">
				<span class="metodo-icon">💳</span>
				<span class="metodo-label">Tarjeta</span>
				<span class="metodo-valor">{recaudadoTarjeta.toFixed(2)}€</span>
			</div>
			<div class="metodo-sep">│</div>
			<div class="metodo-item">
				<span class="metodo-icon">💵</span>
				<span class="metodo-label">Efectivo</span>
				<span class="metodo-valor">{recaudadoEfectivo.toFixed(2)}€</span>
			</div>
		</div>

		<!-- Barra de progreso -->
		<div class="progress-bar">
			<div class="progress-fill" style="width:{pctPagado}%"></div>
		</div>
		<div class="text-muted text-sm" style="text-align:right;margin-top:.25rem">
			{pctPagado}% cobrado
		</div>
	</div>

	<!-- Lista de jugadores -->
	<div class="jugadores-lista">
		{#each jugadoresOrdenados as jug}
		<div class="jugador-cobro" class:pagado={jug.pagado}>

		<!-- Info del jugador (tap → extras) -->
			<button class="jugador-info" onclick={() => abrirExtras(jug)}>
				<span class="pista-chip pista-{jug.nivel}">{jug.nivel}</span>
				<div class="jugador-texto">
					<div class="jugador-nombre">{jug.nombre}</div>
					<div class="jugador-detalle">
						{#if jug.pista_asignada}
						<span class="badge badge-accent">P{jug.pista_asignada}</span>
						{/if}
						{#if jug.pagado}
						<span class="badge" class:badge-blue={jug.metodo_pago==='tarjeta'} class:badge-amber={jug.metodo_pago==='efectivo'}>
							{jug.metodo_pago === 'tarjeta' ? '💳 Tarjeta' : jug.metodo_pago === 'efectivo' ? '💵 Efectivo' : '✔ Pagado'}
						</span>
						{/if}
						{#if jug.extras.length > 0}
						<span class="badge badge-amber">+{jug.extras.length} extra{jug.extras.length > 1 ? 's' : ''}</span>
						{/if}
					</div>
				</div>
				<div class="jugador-importe">
					{jug.precio_total.toFixed(2)} €
				</div>
			</button>

			<!-- Dos botones pago + el de semana que viene -->
			<div class="btns-cobro">
				<button
					class="btn-cobro btn-tarjeta"
					class:activo={jug.pagado && jug.metodo_pago === 'tarjeta'}
					onclick={() => marcarPago(jug, 'tarjeta')}
					aria-label="Pagar con tarjeta"
					title="Tarjeta"
				>💳</button>
				<button
					class="btn-cobro btn-efectivo"
					class:activo={jug.pagado && jug.metodo_pago === 'efectivo'}
					onclick={() => marcarPago(jug, 'efectivo')}
					aria-label="Pagar con efectivo"
					title="Efectivo"
				>💵</button>
				<button
					class="btn-cobro btn-semana"
					class:activo={semanaQueViene.has(jug.inscripcion_id)}
					onclick={() => toggleSemana(jug.inscripcion_id)}
					aria-label="Apuntar semana que viene"
					title="Semana que viene"
				>📋</button>
			</div>
		</div>
		{/each}
	</div>

	<!-- Panel semana que viene -->
	{#if datos}
	<div class="semana-panel">
		<button
			class="semana-toggle"
			onclick={() => showSemanaPanel = !showSemanaPanel}
			aria-expanded={showSemanaPanel}
		>
			<span>📋 Semana que viene</span>
			{#if semanaQueViene.size > 0}
			<span class="semana-count">{semanaQueViene.size}</span>
			{/if}
			<span class="semana-arrow" class:open={showSemanaPanel}>▾</span>
		</button>

		{#if showSemanaPanel}
		<div class="semana-body">
			{#if listaSemana.length === 0}
				<p class="text-muted text-sm">Toca el icono 📋 en cada jugador para marcarlo.</p>
			{:else}
				<ol class="semana-lista">
					{#each listaSemana as j}
					<li>
						<span class="pista-chip pista-{j.nivel}">{j.nivel}</span>
						{j.nombre}
						<button class="btn-unsemana" onclick={() => toggleSemana(j.inscripcion_id)} title="Quitar">✕</button>
					</li>
					{/each}
				</ol>
			{/if}
		</div>
		{/if}
	</div>
	{/if}

	{:else if torneoId}
	<div class="empty">
		<p>No hay datos de cobros para este torneo.<br>Asegúrate de que hay jugadores confirmados.</p>
	</div>
	{:else}
	<div class="empty">
		<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
			<circle cx="12" cy="12" r="9"/><path d="M12 6v1m0 10v1M9.5 9.5c0-1.1.9-2 2.5-2s2.5.9 2.5 2-1.1 2-2.5 2-2.5.9-2.5 2 .9 2 2.5 2 2.5-.9 2.5-2"/>
		</svg>
		<p>Selecciona un torneo para gestionar los cobros.</p>
	</div>
	{/if}
</div>

<style>
/* ── Stats ───────────────────────────────────────────── */
.cobros-stats {
	background: var(--bg-2);
	border: 1px solid var(--bg-3);
	border-radius: var(--radius);
	padding: 1rem;
	margin-bottom: 1rem;
}
.stats-row {
	display: grid;
	grid-template-columns: repeat(4, 1fr);
	gap: .5rem;
	margin-bottom: .75rem;
}
.stat { text-align: center; }
.stat-num   { display: block; font-size: 1.5rem; font-weight: 800; line-height: 1.1; }
.stat-label { display: block; font-size: .7rem; color: var(--text-2); margin-top: .15rem; }

.progress-bar {
	height: 6px;
	background: var(--bg-3);
	border-radius: 99px;
	overflow: hidden;
}
.progress-fill {
	height: 100%;
	background: linear-gradient(90deg, var(--accent), var(--green));
	border-radius: 99px;
	transition: width .4s ease;
}

/* ── Lista ───────────────────────────────────────────── */
.jugadores-lista {
	display: flex;
	flex-direction: column;
	gap: .5rem;
	padding-bottom: 2rem;
}

.jugador-cobro {
	display: flex;
	align-items: stretch;
	background: var(--bg-2);
	border: 1px solid var(--bg-3);
	border-radius: var(--radius);
	overflow: hidden;
	transition: border-color .15s, opacity .15s;
}
.jugador-cobro.pagado {
	border-color: rgba(34,197,94,.3);
	opacity: .75;
}

.jugador-info {
	flex: 1;
	display: flex;
	align-items: center;
	gap: .65rem;
	padding: .75rem .85rem;
	background: none;
	border: none;
	color: inherit;
	font-family: inherit;
	cursor: pointer;
	text-align: left;
	transition: background .12s;
}
.jugador-info:hover  { background: rgba(255,255,255,.03); }
.jugador-info:active { background: rgba(255,255,255,.06); }

.jugador-texto { flex: 1; }
.jugador-nombre { font-weight: 600; font-size: .95rem; }
.jugador-detalle {
	display: flex; gap: .3rem; margin-top: .2rem; flex-wrap: wrap;
}

.jugador-importe {
	font-size: .9rem; font-weight: 600; color: var(--text-1); white-space: nowrap;
}

/* Botones de método de pago — dos botones verticales */
.btns-cobro {
	display: flex;
	flex-direction: column;
	border-left: 1px solid var(--bg-3);
	flex-shrink: 0;
}
.btn-cobro {
	width: 52px;
	flex: 1;
	border: none;
	background: transparent;
	font-size: 1.25rem;
	cursor: pointer;
	transition: all .12s;
	display: flex;
	align-items: center;
	justify-content: center;
	opacity: .45;
	filter: grayscale(1);
}
.btn-cobro:active { transform: scale(.88); }
.btn-cobro.activo {
	opacity: 1;
	filter: none;
	background: rgba(255,255,255,.06);
}
.btn-tarjeta.activo  { background: rgba(59,130,246,.15); }
.btn-efectivo.activo { background: rgba(34,197,94,.15); }

.btn-tarjeta  { border-bottom: 1px solid var(--bg-3); }

/* ── WS dot indicator ────────────────────────────────── */
.ws-dot {
	width: 10px; height: 10px;
	border-radius: 50%;
	box-shadow: 0 0 6px currentColor;
	transition: background .3s;
	flex-shrink: 0;
}

/* ── Modal de extras ─────────────────────────────────── */
.modal-overlay {
	position: fixed; inset: 0;
	background: rgba(0,0,0,.7);
	backdrop-filter: blur(4px);
	z-index: 200;
	display: flex; align-items: flex-end; justify-content: center;
	padding: 1rem;
}
@media (min-width: 480px) {
	.modal-overlay { align-items: center; }
}
.modal {
	background: var(--bg-2);
	border: 1px solid var(--bg-3);
	border-radius: var(--radius-lg) var(--radius-lg) var(--radius-sm) var(--radius-sm);
	padding: 1.25rem;
	width: 100%; max-width: 440px;
	max-height: 80dvh;
	overflow-y: auto;
}
@media (min-width: 480px) {
	.modal { border-radius: var(--radius-lg); }
}
.modal-header {
	display: flex; align-items: center; justify-content: space-between;
	margin-bottom: 1rem;
}

.extras-list { display: flex; flex-direction: column; gap: .4rem; margin-bottom: .5rem; }
.extra-row {
	display: flex; align-items: center; gap: .5rem;
	background: var(--bg-0); border-radius: var(--radius-sm); padding: .5rem .75rem;
}
.extra-concepto { flex: 1; font-size: .9rem; }
.extra-precio { font-weight: 600; color: var(--accent); white-space: nowrap; }
.extra-total {
	text-align: right; font-size: .85rem; color: var(--text-1); padding: .25rem .25rem 0;
}

/* Desglose tarjeta/efectivo */
.metodo-row {
	display: flex; align-items: center; justify-content: center;
	gap: .5rem; margin-bottom: .75rem;
	font-size: .8rem;
}
.metodo-item { display: flex; align-items: center; gap: .3rem; }
.metodo-icon { font-size: 1rem; }
.metodo-label { color: var(--text-2); }
.metodo-valor { font-weight: 700; color: var(--text-1); }
.metodo-sep { color: var(--bg-3); font-size: 1.2rem; }

/* Badge extra colors */
.badge-blue   { background: rgba(59,130,246,.2);  color: #60a5fa; }

/* ── Semana que viene ────────────────────────────────── */
.btn-semana.activo { background: rgba(168,85,247,.2) !important; filter: none; opacity: 1; }
.btn-tarjeta  { border-bottom: 1px solid var(--bg-3); }
.btn-semana   { border-top: 1px solid var(--bg-3); }

.semana-panel {
	margin-top: 1rem;
	background: var(--bg-2);
	border: 1px solid var(--bg-3);
	border-radius: var(--radius);
	overflow: hidden;
}
.semana-toggle {
	width: 100%; display: flex; align-items: center; gap: .5rem;
	padding: .75rem 1rem; background: none; border: none;
	color: inherit; font-family: inherit; font-size: .9rem; font-weight: 600;
	cursor: pointer; text-align: left;
	transition: background .12s;
}
.semana-toggle:hover { background: rgba(255,255,255,.04); }
.semana-count {
	background: rgba(168,85,247,.25); color: #c084fc;
	border-radius: 99px; font-size: .75rem; font-weight: 700;
	padding: .1rem .5rem; min-width: 1.4rem; text-align: center;
}
.semana-arrow { margin-left: auto; font-size: .85rem; transition: transform .2s; }
.semana-arrow.open { transform: rotate(180deg); }
.semana-body {
	border-top: 1px solid var(--bg-3);
	padding: .75rem 1rem;
}
.semana-lista {
	list-style: none; padding: 0; margin: 0;
	display: flex; flex-direction: column; gap: .4rem;
}
.semana-lista li {
	display: flex; align-items: center; gap: .5rem;
	font-size: .9rem;
}
.semana-lista li span { flex-shrink: 0; }
.btn-unsemana {
	margin-left: auto; background: none; border: none;
	color: var(--text-2); cursor: pointer; font-size: .85rem;
	padding: .1rem .3rem; border-radius: 4px;
	transition: color .1s, background .1s;
}
.btn-unsemana:hover { color: var(--red); background: rgba(248,113,113,.1); }
</style>
