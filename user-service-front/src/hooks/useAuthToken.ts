import { useCallback, useEffect, useState } from 'react';
import { TOKEN_KEY, logout as apiLogout } from '../api/client';

export function useAuthToken(): [boolean, () => void] {
  const [hasToken, setHasToken] = useState(() => !!localStorage.getItem(TOKEN_KEY));

  const logout = useCallback(() => {
    void apiLogout().finally(() => {
      localStorage.removeItem(TOKEN_KEY);
      setHasToken(false);
    });
  }, []);

  useEffect(() => {
    const onStorage = () => setHasToken(!!localStorage.getItem(TOKEN_KEY));
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  return [hasToken, logout];
}
