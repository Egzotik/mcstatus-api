from flask import Flask, jsonify, Response
from flask_cors import CORS
from mcstatus import MinecraftServer
import requests
import threading
import time
from datetime import datetime, timezone


app = Flask(__name__)
CORS(app) #, resources={r"/api/*": {"origins": ["https://egzotik.github.io", "https://egzotik.github.io/mixmonitoring/"]}})

SERVER_CONFIG = {
    "ip": "88.99.104.215",
    "port": 25566,
    "version": "1.5.2",
    "max_players": 100
}

activity_log = []
player_set = set()
daily_peaks = {
    'today': 0,
    'yesterday': 0,
    'date': datetime.utcnow().date()
}

def get_server_status():
    try:
        server = MinecraftServer(SERVER_CONFIG['ip'], SERVER_CONFIG['port'])

        try:
            query = server.query()
            motd = query.motd if query else "Сервер недоступен"
            player_names = query.players.names if query and query.players.names else []
            online_count = len(player_names)
        except:
            query = None
            motd = "Query недоступен"
            player_names = []
            online_count = 0

        return {
            "status": "online" if query else "offline",
            "version": SERVER_CONFIG["version"],
            "players": {
                "online": online_count,
                "max": SERVER_CONFIG["max_players"],
                "list": player_names
            },
            "motd": motd
        }

    except:
        return {
            "status": "offline",
            "version": None,
            "players": {
                "online": 0,
                "max": SERVER_CONFIG["max_players"],
                "list": []
            },
            "motd": "Ошибка подключения к серверу"
        }

def monitor_players():
    global player_set, activity_log, daily_peaks

    while True:
        status = get_server_status()
        if status['status'] == 'online':
            current_players = set(status['players']['list'])

            joined = current_players - player_set
            for player in joined:
                activity_log.append({
                    'player': player,
                    'action': 'joined',
                    'time': datetime.now(timezone.utc).isoformat()

                })

            left = player_set - current_players
            for player in left:
                activity_log.append({
                    'player': player,
                    'action': 'left',
                    'time': datetime.now(timezone.utc).isoformat()

                })

            player_set = current_players

            today = datetime.now(timezone.utc).date()
            if daily_peaks['date'] != today:
                daily_peaks['yesterday'] = daily_peaks['today']
                daily_peaks['today'] = 0
                daily_peaks['date'] = today

            daily_peaks['today'] = max(daily_peaks['today'], len(current_players))

            if len(activity_log) > 100:
                activity_log = activity_log[-100:]

        time.sleep(1)

threading.Thread(target=monitor_players, daemon=True).start()

@app.route('/api/status')
def api_status():
    return jsonify(get_server_status())

@app.route('/api/player_head/<string:player_name>')
def player_head(player_name):
    url = f"https://files.mix-servers.com/web/skins/{player_name}.png"
    r = requests.get(url)
    if r.status_code != 200:
        return Response(status=404)
    return Response(r.content, mimetype='image/png',
                    headers={"Cache-Control": "public, max-age=3600"})

@app.route('/api/activity')
def api_activity():
    return jsonify(activity_log[-10:][::-1])

@app.route('/api/peak')
def api_peak():
    return jsonify({
        'today': daily_peaks['today'],
        'yesterday': daily_peaks['yesterday']
    })

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
