// Run: docker compose exec -T result node < scripts/socket-smoke.js
const connect = require('socket.io-client')
const socket = connect(process.env.RESULT_URL || 'http://127.0.0.1:8888', {transports: ['websocket']})
const timer = setTimeout(() => { console.error('Timeout WebSocket'); process.exit(1) }, 10000)
const expected = process.env.EXPECTED_SCORES ? JSON.parse(process.env.EXPECTED_SCORES) : null
socket.on('scores', payload => {
  const scores = JSON.parse(payload)
  if (!Number.isInteger(scores.a) || !Number.isInteger(scores.b)) process.exit(1)
  if (expected && (scores.a !== expected.a || scores.b !== expected.b)) return
  console.log('OK WebSocket :', scores)
  clearTimeout(timer)
  socket.close()
})
socket.on('connect_error', error => { console.error(error.message); process.exit(1) })
