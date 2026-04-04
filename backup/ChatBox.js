import { useState, useRef, useEffect } from "react";
import { sendMessage } from "../services/api";
import Message from "./Message";

function ChatBox({
  messages,
  setMessages,
  isFullscreen,
  setIsFullscreen,
  closeChat
}) {

  const [input,setInput] = useState("");
  const [typing,setTyping] = useState(false);

  const messagesEndRef = useRef(null);
  const streamingRef = useRef(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({behavior:"smooth"});
  };

  useEffect(()=>{
    scrollToBottom();
  },[messages]);

  const handleSend = async () => {

    if(!input.trim() || streamingRef.current) return;

    const userMessage = {
      role:"user",
      content:input
    };

    setInput("");
    setMessages(prev => [...prev,userMessage]);

    setTyping(true);
    streamingRef.current = true;

    let botMessage = null;
    let firstToken = true;

    try{

      await sendMessage([...messages,userMessage],(token)=>{

        // token rỗng thì bỏ
        if(!token || !token.trim()) return;

        // token đầu tiên
        if(firstToken){

          setTyping(false);

          botMessage = {
            role:"assistant",
            content:token
          };

          setMessages(prev => [...prev,botMessage]);

          firstToken = false;
          return;
        }

        // các token tiếp theo
        botMessage.content += token;

        setMessages(prev => {

          const updated = [...prev];
          updated[updated.length-1] = {...botMessage};
          return updated;

        });

      });

    }catch(err){

      console.error("Chat error:",err);

      setMessages(prev => [
        ...prev,
        {
          role:"assistant",
          content:"Xin lỗi, đã xảy ra lỗi khi xử lý câu hỏi."
        }
      ]);

    }

    streamingRef.current = false;
    setTyping(false);

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
      overflow:"hidden",
      zIndex:999
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
          <Message
            key={i}
            role={m.role}
            content={m.content}
          />
        ))}

        {typing && (
          <Message role="assistant" typing/>
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