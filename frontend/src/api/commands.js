

const ssl = window.location.protocol === "https:"

export default function command(url, command, onmessage, onclose) {
  url = `ws://127.0.0.1:8000/command`
  const token = localStorage.getItem("token");

  let conn = new window.WebSocket(url, token)
  conn.onopen = () => conn.send(command)
  conn.onmessage = onmessage
  conn.onclose = onclose
}
