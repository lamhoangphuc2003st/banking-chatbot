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
        color: isUser ? "white" : "#333",
        padding:"10px 14px",
        borderRadius:12,
        maxWidth:"70%",
        wordWrap:"break-word",
        whiteSpace:"pre-wrap",
        lineHeight:"1.5",
        boxShadow:"0 2px 6px rgba(0,0,0,0.1)"
      }}>

        {typing ? (
          <span className="typing">
            ● ● ●
          </span>
        ) : (
          content
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