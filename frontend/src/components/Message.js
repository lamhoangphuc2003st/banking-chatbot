import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function Message({role,content,typing}){

  const isUser = role === "user";

  return(

    <div style={{
      display:"flex",
      justifyContent: isUser ? "flex-end" : "flex-start",
      alignItems:"flex-end",
      marginBottom:12,
      gap:8
    }}>

      {!isUser && (
        <div style={{
          width:32,
          height:32,
          borderRadius:"50%",
          background:"#16a085",
          display:"flex",
          alignItems:"center",
          justifyContent:"center",
          color:"white",
          fontSize:14
        }}>
          🤖
        </div>
      )}

      <div style={{
        background: isUser ? "#16a085" : "#ffffff",
        color: isUser ? "white" : "#2c3e50",
        padding:"10px 14px",
        borderRadius:12,
        maxWidth:"70%",
        wordWrap:"break-word",
        lineHeight:"1.5",
        boxShadow:"0 2px 6px rgba(0,0,0,0.1)"
      }}>

        {typing ? (
          <span className="typing">
            ● ● ●
          </span>
        ) : (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              h1: ({children}) => (
                <div style={{fontSize:16,fontWeight:700,margin:"8px 0 4px"}}>
                  {children}
                </div>
              ),

              h2: ({children}) => (
                <div style={{fontSize:15,fontWeight:700,margin:"8px 0 4px"}}>
                  {children}
                </div>
              ),

              h3: ({children}) => (
                <div style={{fontSize:14,fontWeight:600,margin:"6px 0 2px"}}>
                  {children}
                </div>
              ),

              p: ({children}) => (
                <span>{children}</span>
              ),

              ul: ({children}) => (
                <ul style={{
                  margin:"4px 0",
                  paddingLeft:0,
                  listStyle:"none"
                }}>
                  {children}
                </ul>
              ),

              ol: ({children}) => (
                <ol style={{
                  margin:"4px 0",
                  paddingLeft:18
                }}>
                  {children}
                </ol>
              ),

              li: ({children}) => (
                <li style={{margin:"2px 0"}}>
                  • {children}
                </li>
              ),

              strong: ({children}) => (
                <strong style={{fontWeight:600}}>
                  {children}
                </strong>
              )
            }}
          >
            {content}
          </ReactMarkdown>
        )}

      </div>

      {isUser && (
        <div style={{
          width:32,
          height:32,
          borderRadius:"50%",
          background:"#bdc3c7",
          display:"flex",
          alignItems:"center",
          justifyContent:"center",
          fontSize:14
        }}>
          👤
        </div>
      )}

    </div>

  );

}

export default Message;