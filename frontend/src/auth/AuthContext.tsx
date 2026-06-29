import { createContext, useEffect, useState, type ReactNode } from 'react';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000';

type User = {
  id: string;
  username: string;
  email: string;
};

export type AuthContextType = {
  user: User | null;
  login: () => void;
  logout: () => void;
  isAuthenticated: boolean;
  isLoading: boolean;
};

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loginTrigger, setLoginTrigger] = useState(0);

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/users/me`, {
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
          },
        });
        if (res.ok) {
          const data = await res.json();
          setUser(data);
        } else {
          setUser(null);
        }
      } catch (error) {
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };
    fetchUser();
  }, [loginTrigger]);

  const login = () => {
    setLoginTrigger(c => c + 1);
  };

  const logout = async () => {
    setUser(null);
    try {
        await fetch(`${API_BASE_URL}/api/auth/logout`, {
            method: 'POST',
            credentials: 'include',
        });
    } catch (error) {
        // If logout API fails, the user is already logged out on the client.
    }
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, isAuthenticated: !!user, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};

