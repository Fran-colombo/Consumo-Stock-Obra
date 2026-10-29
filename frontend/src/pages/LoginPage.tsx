import { FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorText, PasswordField } from "../components/ui";

export function LoginPage() {
  const { user, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
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
          <img className="brand-mark" src="/favicon.svg" alt="" width={34} height={34} />
          <div>
            <strong>Consumo Stock en Obra</strong>
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
          <PasswordField id="pass" value={password} onChange={setPassword} autoComplete="current-password" required />
        </div>
        <button className="btn" type="submit" style={{ marginTop: 16 }}>Entrar</button>
      </form>
    </div>
  );
}
