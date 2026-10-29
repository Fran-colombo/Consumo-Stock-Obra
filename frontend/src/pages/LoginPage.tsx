import { FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorText } from "../components/ui";

export function LoginPage() {
  const { user, login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  if (user) return <Navigate to="/" replace />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo ingresar.");
    }
  }

  return (
    <div className="login-wrap">
      <form className="card login-card" onSubmit={onSubmit}>
        <div className="brand" style={{ marginBottom: 16 }}>
          <div className="brand-mark" aria-hidden="true" />
          <div>
            <strong>Conkreto</strong>
            <span>Control de materiales</span>
          </div>
        </div>
        <h1>Ingresar</h1>
        <p className="hint">Cada movimiento queda asociado a la persona que inicia sesión.</p>
        {error ? <ErrorText error={error} /> : null}
        <div className="field">
          <label htmlFor="user">Usuario</label>
          <input id="user" value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required />
        </div>
        <div className="field" style={{ marginTop: 12 }}>
          <label htmlFor="pass">Contraseña</label>
          <input id="pass" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required />
        </div>
        <button className="btn" type="submit" style={{ marginTop: 16 }}>Entrar</button>
      </form>
    </div>
  );
}
