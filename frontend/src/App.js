import "./App.css";
import ChatWidget from "./components/ChatWidget";

function App() {
  return (
    <div style={{ minHeight: "100vh", background: "#f5f6fa" }}>

      <div style={{
        minHeight: "100vh",
        background: "#f5f6fa",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 28,
        fontWeight: "bold"
      }}>
        Banking AI Assistant
      </div>

      <ChatWidget />

      <footer className="footer">
        © 2026 Lam Hoang Phuc • Banking RAG Chatbot
      </footer>

    </div>
  );
}

export default App;