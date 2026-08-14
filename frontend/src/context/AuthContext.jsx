import { createContext, useCallback, useContext, useEffect, useState } from "react";
import * as apiClient from "../api/client.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [account, setAccount] = useState(null);
  const [loading, setLoading] = useState(true);

  // On mount, if a token exists, try to resolve the current account.
  useEffect(() => {
    let active = true;
    async function bootstrap() {
      if (!apiClient.getToken()) {
        setLoading(false);
        return;
      }
      try {
        const me = await apiClient.fetchMe();
        if (active) setAccount(me);
      } catch {
        apiClient.setToken(null); // stale/expired token
      } finally {
        if (active) setLoading(false);
      }
    }
    bootstrap();
    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (email, password) => {
    const data = await apiClient.login(email, password);
    apiClient.setToken(data.access_token);
    setAccount(data.account);
    return data.account;
  }, []);

  const register = useCallback(async (email, password) => {
    const data = await apiClient.register(email, password);
    apiClient.setToken(data.access_token);
    setAccount(data.account);
    // Return the full response so the caller can see verification_status +
    // dev_verification_code and skip the verify step when auto-verified.
    return data;
  }, []);

  const logout = useCallback(() => {
    apiClient.setToken(null);
    setAccount(null);
  }, []);

  const verifyEmail = useCallback(async (email, code) => {
    await apiClient.verifyEmail(email, code);
    // Optimistically flip the local flag so the UI updates.
    setAccount((cur) => (cur ? { ...cur, email_verified: true } : cur));
  }, []);

  const resendVerification = useCallback(async (email) => {
    return apiClient.resendVerification(email);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        account,
        isAuthed: !!account,
        emailVerified: !!account?.email_verified,
        loading,
        login,
        register,
        logout,
        verifyEmail,
        resendVerification,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
