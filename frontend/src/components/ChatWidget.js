import { useState } from "react";
import ChatBox from "./ChatBox";

function ChatWidget(){

  const [open,setOpen] = useState(false);
  const [messages,setMessages] = useState([]);
  const [isFullscreen,setIsFullscreen] = useState(false);

  return(

    <div style={{
      position:"fixed",
      bottom:20,
      right:20,
      zIndex:9999
    }}>

      {open && (
        <ChatBox
          messages={messages}
          setMessages={setMessages}
          isFullscreen={isFullscreen}
          setIsFullscreen={setIsFullscreen}
          closeChat={()=>setOpen(false)}
        />
      )}

      {!open && (
        <button
          onClick={()=>setOpen(true)}
          style={{
            width:60,
            height:60,
            borderRadius:"50%",
            background:"#16a085",
            color:"white",
            border:"none",
            fontSize:24,
            cursor:"pointer"
          }}
        >
          💬
        </button>
      )}

    </div>

  );

}

export default ChatWidget;