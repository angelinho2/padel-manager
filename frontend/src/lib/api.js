/**
 * lib/api.js — Cliente HTTP centralizado para llamar al backend
 *
 * Todas las peticiones al backend pasan por aquí.
 * - En desarrollo: /api/* se redirige a http://localhost:8001 (via vite proxy)
 * - En producción: /api/* lo gestiona Caddy que lo redirige al backend
 *
 * El token JWT se incluye automáticamente en cada petición.
 */

const BASE = '/api';

/** Lee el token guardado en localStorage */
function getToken() {
	if (typeof localStorage === 'undefined') return null;
	return localStorage.getItem('token');
}

/** Cabeceras estándar con el token JWT */
function headers(extra = {}) {
	const token = getToken();
	return {
		'Content-Type': 'application/json',
		...(token ? { Authorization: `Bearer ${token}` } : {}),
		...extra
	};
}

/** Petición genérica */
async function request(method, path, body) {
	const res = await fetch(`${BASE}${path}`, {
		method,
		headers: headers(),
		...(body !== undefined ? { body: JSON.stringify(body) } : {})
	});

	if (res.status === 401) {
		// Token expirado: borrar y redirigir al login
		localStorage.removeItem('token');
		window.location.href = '/login';
		return;
	}

	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: res.statusText }));
		throw new Error(err.detail || `Error ${res.status}`);
	}

	if (res.status === 204) return null; // No Content
	return res.json();
}

const get  = (path)        => request('GET',    path);
const post = (path, body)  => request('POST',   path, body);
const patch = (path, body) => request('PATCH',  path, body);
const del  = (path)        => request('DELETE', path);

// ── Auth ──────────────────────────────────────────────────────

export async function login(username, password) {
	// El endpoint de login usa form data (estándar OAuth2)
	const res = await fetch(`${BASE}/auth/login`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
		body: `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`
	});
	if (!res.ok) {
		const err = await res.json().catch(() => ({}));
		throw new Error(err.detail || 'Credenciales incorrectas');
	}
	const data = await res.json();
	localStorage.setItem('token', data.access_token);
	return data;
}

export function logout() {
	localStorage.removeItem('token');
	window.location.href = '/login';
}

export function isLoggedIn() {
	return !!getToken();
}

// ── Jugadores ─────────────────────────────────────────────────

export const jugadores = {
	listar: (params = {}) => {
		const q = new URLSearchParams(params).toString();
		return get(`/jugadores/${q ? '?' + q : ''}`);
	},
	crear: (datos)          => post('/jugadores/', datos),
	obtener: (id)           => get(`/jugadores/${id}`),
	actualizar: (id, datos) => patch(`/jugadores/${id}`, datos),
	eliminar: (id)          => del(`/jugadores/${id}`),
	historial: (id)         => get(`/jugadores/${id}/historial`)
};

// ── Torneos ───────────────────────────────────────────────────

export const torneos = {
	listar: ()            => get('/torneos/'),
	crear: (datos)        => post('/torneos/', datos),
	obtener: (id)         => get(`/torneos/${id}`),
	estado: (id, estado)  => patch(`/torneos/${id}/estado`, { estado }),
	eliminar: (id)        => del(`/torneos/${id}`),
};

// ── Inscripciones ─────────────────────────────────────────────

export const inscripciones = {
	apuntar: (torneoId, datos)    => post(`/torneos/${torneoId}/inscripciones`, datos),
	listar: (torneoId)            => get(`/torneos/${torneoId}/inscripciones`),
	baja: (id)                    => patch(`/inscripciones/${id}/baja`),
	togglePago: (id, metodo)      => patch(`/inscripciones/${id}/pago`, { metodo: metodo ?? null }),
	agregarExtra: (id, datos)     => post(`/inscripciones/${id}/extras`, datos),
	eliminarExtra: (extraId)      => del(`/extras/${extraId}`)
};

// ── Pistas ────────────────────────────────────────────────────

export const pistas = {
	generar: (torneoId)               => post(`/torneos/${torneoId}/generar-pistas`),
	ver: (torneoId)                   => get(`/torneos/${torneoId}/pistas`),
	guardar: (torneoId, pistasData)   => patch(`/torneos/${torneoId}/pistas`, { pistas: pistasData }),
	publicar: (torneoId)              => patch(`/torneos/${torneoId}/publicar-pistas`)
};
