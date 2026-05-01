import type { ReactNode } from 'react';
import { useEffect } from 'react';
import { Navigate, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import LoginPage from './pages/Login';
import UsersPage from './pages/Users';
import RolesPage from './pages/Roles';
import PermissionsPage from './pages/Permissions';
import { AdminLayout } from './layouts/AdminLayout';
import { useAuthToken } from './hooks/useAuthToken';

function RequireAuth({ children }: { children: ReactNode }) {
  const [hasToken] = useAuthToken();
  const location = useLocation();
  if (!hasToken) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return children;
}

function LoginRoute() {
  const [hasToken] = useAuthToken();
  const navigate = useNavigate();
  useEffect(() => {
    if (hasToken) {
      void navigate('/users', { replace: true });
    }
  }, [hasToken, navigate]);

  return <LoginPage />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginRoute />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <AdminLayout>
              <Outlet />
            </AdminLayout>
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/users" replace />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="roles" element={<RolesPage />} />
        <Route path="permissions" element={<PermissionsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/users" replace />} />
    </Routes>
  );
}
