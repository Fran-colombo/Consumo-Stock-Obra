import { FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorText } from "../components/ui";

export function LoginPage() {
  const { user, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  if (user) return <Navigate to="/" replace />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await login(email, password);
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
          <label htmlFor="email">Correo</label>
          <input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required />
        </div>
        <div className="field" style={{ marginTop: 12 }}>
          <label htmlFor="pass">Contraseña</label>
          <div className="password-row">
            <input id="pass" type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required />
            <button className="btn ghost" type="button" aria-pressed={showPassword} onClick={() => setShowPassword((visible) => !visible)}>
              {showPassword ? "Ocultar" : "Mostrar"}
            </button>
          </div>
        </div>
        <button className="btn" type="submit" style={{ marginTop: 16 }}>Entrar</button>
      </form>
    </div>
  );
}
