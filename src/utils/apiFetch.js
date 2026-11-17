let authTokenGetter = null;

export const setAuthTokenGetter = (getToken) => {
  authTokenGetter = getToken;
};

export const apiFetch = async (input, init = {}) => {
  const headers = new Headers(init.headers || {});
  if (authTokenGetter) {
    const token = await authTokenGetter();
    if (token) headers.set('Authorization', `Bearer ${token}`);
  }

  return fetch(input, { ...init, headers });
};
