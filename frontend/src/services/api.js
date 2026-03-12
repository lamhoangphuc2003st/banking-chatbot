export async function sendMessage(messages){

  const res = await fetch("http://localhost:8000/chat",{
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