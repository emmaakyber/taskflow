// Thin client over the Flask API. Every function resolves to parsed JSON or
// throws an ApiError carrying the server's own message, so the UI can show
// "Field 'title' must not be empty." instead of a generic failure.

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...options.headers },
      ...options,
    });
  } catch {
    throw new ApiError(0, "network_error", "Could not reach the server.");
  }

  if (res.status === 204) return null;

  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error ?? {};
    throw new ApiError(res.status, err.code ?? "error", err.message ?? `Request failed (${res.status})`);
  }
  return body;
}

export const listTasks = (status = "all") => request(`/tasks?status=${status}`);
export const createTask = (title) => request("/tasks", { method: "POST", body: JSON.stringify({ title }) });
export const completeTask = (id) => request(`/tasks/${id}/complete`, { method: "PUT" });
export const deleteTask = (id) => request(`/tasks/${id}`, { method: "DELETE" });
export const getStats = () => request("/tasks/stats");
