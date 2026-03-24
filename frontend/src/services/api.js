export async function sendMessage(messages, onToken){

  const res = await fetch("http://127.0.0.1:8000/chat",{ //http://127.0.0.1:8000      https://banking-chatbot-oyp8.onrender.com  https://banking-chatbot-1-081l.onrender.com
    method:"POST",
    headers:{
      "Content-Type":"application/json"
    },
    body:JSON.stringify({
      messages:messages
    })
  });

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");

  let done = false;

  while(!done){

    const {value,done:doneReading} = await reader.read();
    done = doneReading;

    const chunk = decoder.decode(value || new Uint8Array());

    if(chunk){
      onToken(chunk);
    }

  }

}