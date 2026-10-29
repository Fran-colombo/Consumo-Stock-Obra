export function formatQty(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  return new Intl.NumberFormat("es-AR", { maximumFractionDigits: 4 }).format(number);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split("-").map(Number);
    return new Intl.DateTimeFormat("es-AR", { dateStyle: "short" }).format(new Date(year, month - 1, day));
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("es-AR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Argentina/Buenos_Aires",
  }).format(date);
}

export function formatPercent(value: string | number | null | undefined, status?: string): string {
  if (status === "NO_CALCULABLE" || value === null || value === undefined || value === "") return "No calculable";
  const number = Number(value);
  if (Number.isNaN(number)) return "No calculable";
  const sign = number > 0 ? "+" : "";
  return `${sign}${new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 }).format(number)} %`;
}

export const STATUS_LABELS: Record<string, string> = {
  PLANIFICADA: "Planificada",
  ACTIVA: "Activa",
  PAUSADA: "Pausada",
  FINALIZADA: "Finalizada",
  CANCELADA: "Cancelada",
  PENDIENTE: "Pendiente",
  EN_CURSO: "En curso",
  BORRADOR: "Borrador",
  CONFIRMADA: "Confirmada",
  PARCIAL: "Parcialmente recibida",
  RECIBIDA: "Recibida",
  REGISTRADA: "Registrada",
  EN_TRANSITO: "En tránsito",
  RECIBIDA_PARCIAL: "Recibida parcial",
  RECIBIDA_CON_DIFERENCIA: "Con diferencia",
  CONFIRMADO: "Confirmado",
  ANULADO: "Anulado",
  DEVUELTA: "Devuelta al origen",
  PERDIDA: "Pérdida registrada",
  DEPOSITO: "Depósito",
  OBRA: "Obra",
  OTRO: "Otra",
};

export const MOVEMENT_LABELS: Record<string, string> = {
  RECEPCION_COMPRA: "Recepción de compra",
  REVERSA_RECEPCION: "Reversa de recepción",
  CONSUMO: "Consumo en obra",
  REVERSA_CONSUMO: "Corrección de consumo",
  TRANSFERENCIA_SALIDA: "Transferencia de salida",
  TRANSFERENCIA_ENTRADA: "Transferencia de entrada",
  TRANSFERENCIA_DEVOLUCION: "Devolución de transferencia",
  AJUSTE: "Ajuste de inventario",
};

export function labelOf(value: string | null | undefined, map: Record<string, string> = STATUS_LABELS): string {
  if (!value) return "—";
  return map[value] || value;
}

export function newKey(): string {
  return crypto.randomUUID();
}
