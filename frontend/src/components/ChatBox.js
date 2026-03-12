import { useState, useRef, useEffect } from "react";
import { sendMessage } from "../services/api";
import Message from "./Message";

function ChatBox({
  messages,
  setMessages,
  isFullscreen,
  setIsFullscreen,
  closeChat
}){

  const [input,setInput] = useState("");
  const [typing,setTyping] = useState(false);

  const messagesEndRef = useRef(null);

  // auto scroll
  useEffect(()=>{
    messagesEndRef.current?.scrollIntoView({behavior:"smooth"});
  },[messages,typing]);

  const handleSend = async ()=>{

    if(!input.trim()) return;

    const userMessage = {
      role:"user",
      content:input
    };

    const newMessages = [...messages,userMessage];

    setMessages(newMessages);
    setInput("");

    setTyping(true);

    const answer = await sendMessage(newMessages);

    const botMessage = {
      role:"assistant",
      content:answer
    };

    setTyping(false);

    setMessages(prev=>[...prev,botMessage]);
  };

  return(

    <div style={{
      position:"fixed",
      bottom: isFullscreen ? 0 : 20,
      right: isFullscreen ? 0 : 20,
      width: isFullscreen ? "100%" : 360,
      height: isFullscreen ? "100%" : 520,
      background:"white",
      borderRadius: isFullscreen ? 0 : 12,
      boxShadow:"0 8px 30px rgba(0,0,0,0.2)",
      display:"flex",
      flexDirection:"column",
      overflow:"hidden"
    }}>

      {/* HEADER */}

      <div style={{
        background:"#16a085",
        color:"white",
        padding:"12px 14px",
        display:"flex",
        justifyContent:"space-between",
        alignItems:"center",
        fontWeight:"bold"
      }}>

        <span>🏦 Banking AI Chatbot</span>

        <div style={{display:"flex",gap:10}}>

          <button
            onClick={()=>setIsFullscreen(!isFullscreen)}
            style={btnStyle}
          >
            {isFullscreen ? "🗗" : "🗖"}
          </button>

          <button
            onClick={closeChat}
            style={btnStyle}
          >
            ✖
          </button>

        </div>

      </div>

      {/* MESSAGES */}

      <div style={{
        flex:1,
        padding:14,
        overflowY:"auto",
        background:"#f5f6fa"
      }}>

        {messages.map((m,i)=>(
          <Message key={i} role={m.role} content={m.content}/>
        ))}

        {typing && (
          <Message role="assistant" content="Đang trả lời..." typing/>
        )}

        <div ref={messagesEndRef}></div>

      </div>

      {/* INPUT */}

      <div style={{
        display:"flex",
        borderTop:"1px solid #eee"
      }}>

        <input
          value={input}
          onChange={(e)=>setInput(e.target.value)}
          placeholder="Nhập tin nhắn..."
          style={{
            flex:1,
            border:"none",
            padding:14,
            outline:"none",
            fontSize:14
          }}
          onKeyDown={(e)=>{
            if(e.key==="Enter") handleSend();
          }}
        />

        <button
          onClick={handleSend}
          style={{
            border:"none",
            background:"#16a085",
            color:"white",
            padding:"0 20px",
            cursor:"pointer",
            fontSize:18
          }}
        >
          ➤
        </button>

      </div>

    </div>

  );

}

const btnStyle = {
  border:"none",
  background:"transparent",
  color:"white",
  cursor:"pointer",
  fontSize:16
};

export default ChatBox;