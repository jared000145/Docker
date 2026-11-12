from flask import Flask, render_template, request, make_response
from redis import Redis
import os
import socket
import secrets
import json
import logging

option_a = os.getenv('OPTION_A', "Cats")
option_b = os.getenv('OPTION_B', "Dogs")
hostname = socket.gethostname()

app = Flask(__name__)

app.logger.setLevel(logging.INFO)

def get_redis():
    if not hasattr(Flask, 'redis'):
        Flask.redis = Redis(host=os.getenv("REDIS_HOST", "redis"),
                            port=int(os.getenv("REDIS_PORT", "6379")),
                            db=0, socket_timeout=5, socket_connect_timeout=5)
    return Flask.redis

@app.route("/health")
def health():
    try:
        get_redis().ping()
        return {"status": "ok"}, 200
    except Exception:
        return {"status": "unavailable"}, 503


@app.route("/", methods=['POST', 'GET'])
def hello():
    voter_id = request.cookies.get('voter_id')
    if not voter_id:
        voter_id = secrets.token_hex(16)

    vote = None

    if request.method == 'POST':
        redis = get_redis()
        vote = request.form.get('vote')
        if vote not in ('a', 'b'):
            return {"error": "Vote invalide"}, 400
        app.logger.info('Received vote for %s', vote)
        data = json.dumps({'voter_id': voter_id, 'vote': vote})
        redis.rpush('votes', data)

    resp = make_response(render_template(
        'index.html',
        option_a=option_a,
        option_b=option_b,
        hostname=hostname,
        vote=vote,
    ))
    resp.set_cookie('voter_id', voter_id, httponly=True, samesite='Lax')
    return resp

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)
