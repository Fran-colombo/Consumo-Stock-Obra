import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { ConsumptionsPage } from "./pages/ConsumptionsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { InventoryPage } from "./pages/InventoryPage";
import { LoginPage } from "./pages/LoginPage";
import { ManualPage } from "./pages/ManualPage";
import { MaterialsPage } from "./pages/MaterialsPage";
import { OrderDetailPage } from "./pages/OrderDetailPage";
import { OrdersPage } from "./pages/OrdersPage";
import { ReportsPage } from "./pages/ReportsPage";
import { RubricsPage } from "./pages/RubricsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TransferDetailPage } from "./pages/TransferDetailPage";
import { TransfersPage } from "./pages/TransfersPage";
import { WorkDetailPage } from "./pages/WorkDetailPage";
import { WorksPage } from "./pages/WorksPage";

function Private() {
  const { user, loading } = useAuth();
  if (loading) return <p className="content">Cargando sesión…</p>;
  if (!user) return <Navigate to="/login" replace />;
  return <Layout />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<Private />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/obras" element={<WorksPage />} />
        <Route path="/obras/:id" element={<WorkDetailPage />} />
        <Route path="/rubros" element={<RubricsPage />} />
        <Route path="/materiales" element={<MaterialsPage />} />
        <Route path="/inventario" element={<InventoryPage />} />
        <Route path="/consumos" element={<ConsumptionsPage />} />
        <Route path="/ordenes" element={<OrdersPage />} />
        <Route path="/ordenes/:id" element={<OrderDetailPage />} />
        <Route path="/transferencias" element={<TransfersPage />} />
        <Route path="/transferencias/:id" element={<TransferDetailPage />} />
        <Route path="/reportes" element={<ReportsPage />} />
        <Route path="/manual" element={<ManualPage />} />
        <Route path="/configuracion" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
