const normalizeBaseUrl = (value: string) => value.replace(/\/+$/, "");

const getDefaultApiBaseUrl = () => {
  if (typeof window === "undefined") {
    return "http://localhost:5000";
  }

  const { hostname, origin } = window.location;
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return "http://localhost:5000";
  }

  return origin;
};

export const API_BASE_URL = normalizeBaseUrl(
  import.meta.env.VITE_API_BASE_URL || getDefaultApiBaseUrl()
);

export const apiUrl = (path: string) => `${API_BASE_URL}${path}`;
