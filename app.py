from flask import Flask, jsonify, Response
from flask_cors import CORS
from mcstatus import MinecraftServer
import requests
import threading
import time
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app) #, resources={r"/api/*": {"origins": ["https://egzotik.github.io", "https://egzotik.github.io/mixmonitoring/"]}})

SERVER_CONFIG = {
    "ip": "88.99.104.215",
    "port": 25566,
    "version": "1.5.2",
    "max_players": 100
}

# Хранилище для логов и пиков
activity_log = []  # [{'player': 'Nick', 'action': 'joined/left', 'time': datetime}]
player_set = set()
daily_peaks = {
    'today': 0,
    'yesterday': 0,
    'date': datetime.utcnow().date()
}

# Получение статуса сервера
def get_server_status():
    try:
        server = MinecraftServer(SERVER_CONFIG['ip'], SERVER_CONFIG['port'])
        query = server.query()
        motd = query.motd if query else "Сервер недоступен"
        return {
            "status": "online" if query else "offline",
            "version": SERVER_CONFIG["version"],
            "players": {
                "online": query.players.online if query else 0,
                "max": SERVER_CONFIG["max_players"],
                "list": query.players.names if query else []
            },
            "motd": motd
        }
    except Exception as e:
        print(f"Ошибка при подключении: {e}")
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

# Фоновый процесс мониторинга
def monitor_players():
    global player_set, activity_log, daily_peaks
    while True:
        status = get_server_status()
        if status['status'] == 'online':
            current_players = set(status['players']['list'])

            # Входы
            joined = current_players - player_set
            for player in joined:
                activity_log.append({
                    'player': player,
                    'action': 'joined',
                    'time': datetime.utcnow().isoformat()
                })

            # Выходы
            left = player_set - current_players
            for player in left:
                activity_log.append({
                    'player': player,
                    'action': 'left',
                    'time': datetime.utcnow().isoformat()
                })

            player_set = current_players

            # Обновление пика онлайна
            today = datetime.utcnow().date()
            if daily_peaks['date'] != today:
                daily_peaks['yesterday'] = daily_peaks['today']
                daily_peaks['today'] = 0
                daily_peaks['date'] = today

            daily_peaks['today'] = max(daily_peaks['today'], len(current_players))

            # Ограничим лог до 100 записей
            if len(activity_log) > 100:
                activity_log = activity_log[-100:]

        time.sleep(1)

# Запуск фонового потока
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
    return jsonify(activity_log[-10:][::-1])  # последние 10 записей, в обратном порядке

@app.route('/api/peak')
def api_peak():
    return jsonify({
        'today': daily_peaks['today'],
        'yesterday': daily_peaks['yesterday']
    })

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
