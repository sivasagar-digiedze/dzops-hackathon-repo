import { useState } from "react";
import { registerUser } from "../api/auth.api";

function RegisterPage({ onAuthSuccess }) {
  const [registerForm, setRegisterForm] = useState({
    name: "",
    email: "",
    password: "",
  });

  const handleSubmit = async (event) => {
    event.preventDefault();
    await registerUser(registerForm);
    onAuthSuccess();
  };

  return (
    <>
      <h2>Registration</h2>
      <form className="form-grid" onSubmit={handleSubmit}>
        <label>
          Name
          <input
            type="text"
            value={registerForm.name}
            onChange={(e) => setRegisterForm((p) => ({ ...p, name: e.target.value }))}
            placeholder="Your name"
          />
        </label>
        <label>
          Email
          <input
            type="email"
            value={registerForm.email}
            onChange={(e) => setRegisterForm((p) => ({ ...p, email: e.target.value }))}
            placeholder="you@example.com"
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={registerForm.password}
            onChange={(e) => setRegisterForm((p) => ({ ...p, password: e.target.value }))}
            placeholder="Create a password"
          />
        </label>
        <button type="submit">Create Account</button>
      </form>
    </>
  );
}

export default RegisterPage;
