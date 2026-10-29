import { useEffect, useId, useState } from "react";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { labelOf } from "../lib/format";

export function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: (props: { id: string; "aria-invalid"?: boolean; "aria-describedby"?: string }) => React.ReactNode;
}) {
  const id = useId();
  const errorId = `${id}-error`;
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children({ id, "aria-invalid": error ? true : undefined, "aria-describedby": error ? errorId : undefined })}
      {error ? <span className="error" id={errorId}>{error}</span> : null}
    </div>
  );
}

export function Badge({ value }: { value: string }) {
  const tone = value.includes("DIFERENCIA") || value === "PARCIAL" || value === "EN_TRANSITO" || value === "PENDIENTE"
    ? "warn"
    : value === "CANCELADA" || value === "ANULADO" || value === "PERDIDA"
      ? "danger"
      : value === "RECIBIDA" || value === "ACTIVA" || value === "CONFIRMADO" || value === "DEVUELTA"
        ? "ok"
        : "info";
  return <span className={`badge ${tone}`}>{labelOf(value)}</span>;
}

export function Empty({ title, text, action }: { title: string; text: string; action?: React.ReactNode }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      <p>{text}</p>
      {action}
    </div>
  );
}

export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-back" role="presentation" onClick={onClose}>
      <div className="panel dialog" role="dialog" aria-modal="true" aria-label={title} onClick={(event) => event.stopPropagation()}>
        <div className="page-head">
          <h2>{title}</h2>
          <button className="btn ghost" type="button" onClick={onClose}>Cerrar</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function ConfirmButton({
  label,
  message,
  onConfirm,
  tone = "warn",
}: {
  label: string;
  message: string;
  onConfirm: () => Promise<void> | void;
  tone?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className={`btn ${tone}`} type="button" onClick={() => setOpen(true)}>{label}</button>
      {open ? (
        <Modal title="Confirmar operación" onClose={() => setOpen(false)}>
          <p>{message}</p>
          <div className="actions">
            <button className="btn secondary" type="button" onClick={() => setOpen(false)}>Volver</button>
            <button
              className="btn warn"
              type="button"
              onClick={async () => {
                await onConfirm();
                setOpen(false);
              }}
            >
              Confirmar
            </button>
          </div>
        </Modal>
      ) : null}
    </>
  );
}

export function ErrorText({ error }: { error: string }) {
  return <div className="alert" role="alert">{error}</div>;
}

export function AdminFix({
  active,
  onVoid,
  onSaveQty,
}: {
  active: boolean;
  onVoid: (reason: string) => Promise<void>;
  onSaveQty?: (quantity: string, reason: string) => Promise<void>;
}) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [qty, setQty] = useState("");
  const [error, setError] = useState("");
  if (user?.role !== "SYSADMIN" || !active) return null;

  async function run(action: () => Promise<void>) {
    setError("");
    try {
      await action();
      setOpen(false);
      setReason("");
      setQty("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar la corrección.");
    }
  }

  if (!open) {
    return <button className="btn ghost" type="button" onClick={() => setOpen(true)}>Corregir o anular</button>;
  }
  return (
    <div className="form-grid">
      {error ? <ErrorText error={error} /> : null}
      <div className="field"><label>Motivo</label><input aria-label="Motivo de corrección" value={reason} onChange={(event) => setReason(event.target.value)} /></div>
      {onSaveQty ? <div className="field"><label>Nueva cantidad</label><input aria-label="Nueva cantidad" value={qty} onChange={(event) => setQty(event.target.value)} /></div> : null}
      <div className="actions">
        {onSaveQty ? <button className="btn secondary" type="button" onClick={() => run(() => onSaveQty(qty, reason))}>Guardar cantidad</button> : null}
        <button className="btn warn" type="button" onClick={() => run(() => onVoid(reason))}>Anular</button>
        <button className="btn ghost" type="button" onClick={() => setOpen(false)}>Cerrar</button>
      </div>
    </div>
  );
}
