export async function sendMessage(messages){

  const res = await fetch("https://banking-chatbot-oyp8.onrender.com/chat",{
    method:"POST",
    headers:{
      "Content-Type":"application/json"
    },
    body:JSON.stringify({
      messages:messages
    })
  });

  const data = await res.json();

  return data.answer;

}