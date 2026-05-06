import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const ADMIN_TOKEN_KEY = 'wnx_admin_token';
const CUSTOMER_TOKEN_KEY = 'wnx_customer_token';
const ADMIN_USER_KEY = 'wnx_admin_user';
const CUSTOMER_USER_KEY = 'wnx_customer_user';

export const adminAuth = {
  getToken: () => localStorage.getItem(ADMIN_TOKEN_KEY),
  setSession: (token, user) => {
    localStorage.setItem(ADMIN_TOKEN_KEY, token);
    localStorage.setItem(ADMIN_USER_KEY, JSON.stringify(user));
  },
  getUser: () => {
    const raw = localStorage.getItem(ADMIN_USER_KEY);
    return raw ? JSON.parse(raw) : null;
  },
  clear: () => {
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    localStorage.removeItem(ADMIN_USER_KEY);
  },
};

export const customerAuth = {
  getToken: () => localStorage.getItem(CUSTOMER_TOKEN_KEY),
  setSession: (token, user) => {
    localStorage.setItem(CUSTOMER_TOKEN_KEY, token);
    localStorage.setItem(CUSTOMER_USER_KEY, JSON.stringify(user));
  },
  getUser: () => {
    const raw = localStorage.getItem(CUSTOMER_USER_KEY);
    return raw ? JSON.parse(raw) : null;
  },
  clear: () => {
    localStorage.removeItem(CUSTOMER_TOKEN_KEY);
    localStorage.removeItem(CUSTOMER_USER_KEY);
  },
};

export const adminApi = axios.create({ baseURL: API });
adminApi.interceptors.request.use((cfg) => {
  const t = adminAuth.getToken();
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

export const customerApi = axios.create({ baseURL: API });
customerApi.interceptors.request.use((cfg) => {
  const t = customerAuth.getToken();
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

export const publicApi = axios.create({ baseURL: API });
