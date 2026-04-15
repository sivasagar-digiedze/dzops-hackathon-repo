import { useState } from "react";
import { loginUser } from "../api/auth.api";

function LoginPage({ onAuthSuccess }) {
  const [loginForm, setLoginForm] = useState({
    email: "",
    password: "",
  });

  const handleSubmit = async (event) => {
    event.preventDefault();
    await loginUser(loginForm);
    onAuthSuccess();
  };

  return (
    <>
      <h2>Login</h2>
      <form className="form-grid" onSubmit={handleSubmit}>
        <label>
          Email
          <input
            type="email"
            value={loginForm.email}
            onChange={(e) => setLoginForm((p) => ({ ...p, email: e.target.value }))}
            placeholder="you@example.com"
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={loginForm.password}
            onChange={(e) => setLoginForm((p) => ({ ...p, password: e.target.value }))}
            placeholder="Enter your password"
          />
        </label>
        <button type="submit">Sign In</button>
      </form>
    </>
  );
}

export default LoginPage;
