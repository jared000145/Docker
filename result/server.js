let express = require("express"),
  async = require("async"),
  pg = require("pg"),
  path = require("path"),
  cookieParser = require("cookie-parser"),
  bodyParser = require("body-parser"),
  methodOverride = require("method-override"),
  app = express(),
  server = require("http").Server(app),
  io = require("socket.io")(server)

io.set("transports", ["websocket"])

const port = 8888

io.sockets.on("connection", function (socket) {

  socket.emit("message", {text: "Welcome!"})

  socket.on("subscribe", function (data) {
    socket.join(data.channel)
  })
})

const pool = new pg.Pool({
  connectionString: process.env.DATABASE_URL ||
    "postgres://postgres:postgres@postgres:5432/postgres",
})

pool.on("error", error => console.error("PostgreSQL pool:", error.message))

async function getVotes() {
  try {
    const result = await pool.query("SELECT vote, COUNT(id) AS count FROM votes GROUP BY vote")
    io.sockets.emit("scores", JSON.stringify(collectVotesFromResult(result)))
  } catch (error) {
    console.error("Waiting for votes table/database:", error.message)
  } finally {
    setTimeout(getVotes, 1000)
  }
}
getVotes()
function collectVotesFromResult(result) {
  const votes = {a: 0, b: 0}

  result.rows.forEach(function (row) {
    votes[row.vote] = parseInt(row.count)
  })

  return votes
}

app.use(cookieParser())
app.use(bodyParser.json())
app.use(bodyParser.urlencoded({extended: false}))
app.use(methodOverride("X-HTTP-Method-Override"))
app.use(function (req, res, next) {
  res.header("Access-Control-Allow-Origin", "*")
  res.header("Access-Control-Allow-Headers", "Origin, X-Requested-With, Content-Type, Accept")
  res.header("Access-Control-Allow-Methods", "PUT, GET, POST, DELETE, OPTIONS")
  next()
})

app.use(express.static(__dirname + "/views"))

app.get("/health", async function (req, res) {
  try {
    await pool.query("SELECT 1")
    res.status(200).json({ status: "ok" })
  } catch (error) {
    res.status(503).json({ status: "unavailable" })
  }
})

app.get("/", function (req, res) {
  res.sendFile(path.resolve(__dirname + "/views/index.html"))
})

server.listen(port, function () {
  const port = server.address().port
  console.log("App running on port " + port)
})
