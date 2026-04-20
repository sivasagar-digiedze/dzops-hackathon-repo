import { useEffect, useState } from "react";
import { sidebarItems } from "./api/endpoints.api";
import AuditTrailPage from "./pages/AuditTrailPage";
import ChatbotPage from "./pages/ChatbotPage";
import ConnectCloudPage from "./pages/ConnectCloudPage";
import CreateOrganizationPage from "./pages/CreateOrganizationPage";
import ListCloudAccountsPage from "./pages/ListCloudAccountsPage";
import ListOrganizationsPage from "./pages/ListOrganizationsPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import TicketsPage from "./pages/TicketsPage";
import Sidebar from "./components/Sidebar";

function App() {
  const [authMode, setAuthMode] = useState(() => localStorage.getItem("authMode") ?? "login");
  const [isAuthenticated, setIsAuthenticated] = useState(
    () => localStorage.getItem("isAuthenticated") === "true"
  );
  const [activePage, setActivePage] = useState(
    () => localStorage.getItem("activePage") ?? "list-orgs"
  );
  const [isChatOpen, setIsChatOpen] = useState(false);
  const mainSidebarItems = sidebarItems.filter((item) => item.id !== "chatbot");

  useEffect(() => {
    localStorage.setItem("authMode", authMode);
  }, [authMode]);

  useEffect(() => {
    localStorage.setItem("isAuthenticated", String(isAuthenticated));
  }, [isAuthenticated]);

  useEffect(() => {
    localStorage.setItem("activePage", activePage);
  }, [activePage]);

  const handleAuthModeChange = (mode) => setAuthMode(mode);

  const handleAuthSuccess = () => {
    setIsAuthenticated(true);
    setActivePage("list-orgs");
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setAuthMode("login");
    setIsChatOpen(false);
  };

  const pageComponents = {
    "create-org": (
      <CreateOrganizationPage
        onCreated={() => setActivePage("list-orgs")}
        onCancel={() => setActivePage("list-orgs")}
      />
    ),
    "connect-cloud": (
      <ConnectCloudPage
        onConnected={() => setActivePage("list-cloud")}
        onCancel={() => setActivePage("list-cloud")}
      />
    ),
    "list-orgs": <ListOrganizationsPage onAddOrganization={() => setActivePage("create-org")} />,
    "list-cloud": <ListCloudAccountsPage onAddCloudAccount={() => setActivePage("connect-cloud")} />,
    "audit-trail": <AuditTrailPage />,
    tickets: <TicketsPage />,
  };

  return (
    <div className="app-shell">
      <header className="navbar">
        <h1>AURA</h1>
        {!isAuthenticated ? (
          <nav>
            <button
              className={authMode === "register" ? "active-nav" : ""}
              onClick={() => handleAuthModeChange("register")}
            >
              Registration
            </button>
            <button
              className={authMode === "login" ? "active-nav" : ""}
              onClick={() => handleAuthModeChange("login")}
            >
              Login
            </button>
          </nav>
        ) : (
          <button onClick={handleLogout}>Logout</button>
        )}
      </header>

      {!isAuthenticated ? (
        <main className="auth-layout">
          <section className="card auth-card">
            {authMode === "register" ? (
              <RegisterPage onAuthSuccess={handleAuthSuccess} />
            ) : (
              <LoginPage onAuthSuccess={handleAuthSuccess} />
            )}
          </section>
        </main>
      ) : (
        <main className="dashboard-layout">
          <Sidebar items={mainSidebarItems} activePage={activePage} onPageChange={setActivePage} />
          <section className={`content-panel ${isChatOpen ? "content-with-chat" : ""}`}>
            {pageComponents[activePage] ?? null}
          </section>
          <button
            className="floating-chat-toggle"
            type="button"
            onClick={() => setIsChatOpen((prev) => !prev)}
            aria-label={isChatOpen ? "Close chat" : "Open chat"}
          >
            {isChatOpen ? "×" : "💬"}
          </button>
          {isChatOpen ? (
            <div className="floating-chatbot">
              <ChatbotPage />
            </div>
          ) : null}
        </main>
      )}
    </div>
  );
}

export default App;
