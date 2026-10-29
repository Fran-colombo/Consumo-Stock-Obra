import { NavLink, Outlet } from "react-router-dom";
import { useState } from "react";
import { useAuth } from "../auth/AuthContext";

const LINKS = [
  ["/", "Inicio", "bi-grid"],
  ["/obras", "Obras", "bi-building"],
  ["/rubros", "Rubros y tareas", "bi-layers"],
  ["/materiales", "Materiales", "bi-box-seam"],
  ["/inventario", "Inventario", "bi-boxes"],
  ["/consumos", "Consumos", "bi-clipboard-check"],
  ["/ordenes", "Órdenes de compra", "bi-cart"],
  ["/transferencias", "Transferir stock", "bi-arrow-left-right"],
  ["/reportes", "Reportes", "bi-bar-chart"],
  ["/manual", "Manual", "bi-book"],
  ["/configuracion", "Configuración", "bi-sliders"],
];

export function Layout() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  return (
    <div className="app-shell">
      <aside className={open ? "sidebar open" : "sidebar"}>
        <div className="brand">
          <img className="brand-mark" src="/favicon.svg" alt="" width={34} height={34} />
          <div>
            <strong>Consumo Stock en Obra</strong>
          </div>
        </div>
        <nav>
          {LINKS.map(([to, label, icon]) => (
            <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")} onClick={() => setOpen(false)}>
              <i className={`bi ${icon}`} aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div>{user?.full_name}</div>
          <div>{user?.role === "SYSADMIN" ? "Administrador" : "Operador"}</div>
          <button className="action ghost" type="button" onClick={logout} style={{ marginTop: 10, color: "white" }}>
            Salir
          </button>
        </div>
      </aside>
      <main className="content">
        <div className="topbar">
          <button className="action secondary menu-btn" type="button" onClick={() => setOpen((value) => !value)}>
            Menú
          </button>
          <strong>Consumo Stock en Obra</strong>
        </div>
        <Outlet />
      </main>
    </div>
  );
}
