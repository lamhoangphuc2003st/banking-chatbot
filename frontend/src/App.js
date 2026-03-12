import ChatWidget from "./components/ChatWidget";

function App() {

  return (
    <div>

      <div style={{
        height: "100vh",
        background: "#f5f6fa",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 28,
        fontWeight: "bold"
      }}>
        Banking AI Assistant
      </div>

      <ChatWidget/>

    </div>
  );

}

export default App;