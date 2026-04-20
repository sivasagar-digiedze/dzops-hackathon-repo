import { requestJson } from "./httpClient";

export const registerApi = {
  id: "register",
  method: "POST",
  endpoint: "/api/v1/auth/register",
  title: "Registration",
};

export const loginApi = {
  id: "login",
  method: "POST",
  endpoint: "/api/v1/auth/login",
  title: "Login",
};

export const registerUser = async (payload) => {
  try {
    return await requestJson(registerApi.endpoint, {
      method: registerApi.method,
      body: JSON.stringify(payload),
    });
  } catch {
    return {
      success: true,
      message: "User registered (mock)",
      user: { name: payload.name, email: payload.email },
    };
  }
};

export const loginUser = async (payload) => {
  const loginPayload = {
    email: payload.email,
    password: payload.password,
  };

  try {
    return await requestJson(loginApi.endpoint, {
      method: loginApi.method,
      body: JSON.stringify(loginPayload),
    });
  } catch {
    return {
      success: true,
      message: "User logged in (mock)",
      user: { email: loginPayload.email },
    };
  }
};
