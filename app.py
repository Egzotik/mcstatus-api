from flask import Flask, jsonify, Response
from flask_cors import CORS
from mcstatus import MinecraftServer
import requests
import threading
import time
from datetime import datetime, timezone, date
from sqlalchemy import create_engine, Column, Integer, String, Date, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import os
from dotenv import load_dotenv

# Загрузка переменных из .env файла
load_dotenv()

app = Flask(__name__)
CORS(app)

# ---------------- DATABASE CONFIG ---------------- #
DB_URL = os.getenv("DATABASE_URL")
# Замените 'jdbc:mysql' на 'mysql' для использования с SQLAlchemy
DB_URL = DB_URL.replace("jdbc:mysql", "mysql+mysqlconnector")
engine = create_engine(DB_URL, pool_recycle=3600, pool_pre_ping=True)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Activity(Base):
    __tablename__ = 'activity_log'
    id = Column(Integer, primary_key=True)
    player = Column(String(32))
    action = Column(String(16))
    time = Column(DateTime, default=datetime.utcnow)

class Peak(Base):
    __tablename__ = 'daily_peaks'
    date = Column(Date, primary_key=True)
    today = Column(Integer, default=0)
    yesterday = Column(Integer, default=0)

Base.metadata.create_all(engine)

# ---------------- SERVER CONFIG ---------------- #
SERVER_CONFIG = {
    "ip": os.getenv("SERVER_IP"),
    "port": int(os.getenv("SERVER_PORT")),
    "version": os.getenv("SERVER_VERSION"),
    "max_players": int(os.getenv("SERVER_MAX_PLAYERS"))
}

player_set = set()

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
    global player_set

    # Восстановим состояние игроков из последнего статуса
    status = get_server_status()
    if status['status'] == 'online':
        player_set = set(status['players']['list'])

    while True:
        status = get_server_status()
        if status['status'] == 'online':
            current_players = set(status['players']['list'])
            joined = current_players - player_set
            left = player_set - current_players

            session = Session()
            try:
                for player in joined:
                    session.add(Activity(player=player, action='joined', time=datetime.now(timezone.utc)))

                for player in left:
                    session.add(Activity(player=player, action='left', time=datetime.now(timezone.utc)))

                today = date.today()
                peak = session.get(Peak, today)
                if not peak:
                    # Перенос вчерашнего пика
                    yesterday_peak = session.query(Peak).order_by(Peak.date.desc()).first()
                    yesterday = yesterday_peak.today if yesterday_peak else 0
                    peak = Peak(date=today, today=len(current_players), yesterday=yesterday)
                    session.add(peak)
                else:
                    peak.today = max(peak.today, len(current_players))

                session.commit()
            except SQLAlchemyError as e:
                print("DB error:", e)
                session.rollback()
            finally:
                session.close()

            player_set = current_players

        time.sleep(1)

def self_ping():
    while True:
        try:
            requests.get("https://mcstatus-api-iena.onrender.com/api/status")
        except Exception as e:
            print("Self-ping error:", e)
        time.sleep(600)

threading.Thread(target=monitor_players, daemon=True).start()
threading.Thread(target=self_ping, daemon=True).start()

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
    session = Session()
    try:
        activities = session.query(Activity).order_by(Activity.time.desc()).limit(10).all()
        return jsonify([
            {
                "player": a.player,
                "action": a.action,
                "time": a.time.isoformat()
            } for a in activities
        ])
    finally:
        session.close()

@app.route('/api/peak')
def api_peak():
    session = Session()
    try:
        today = session.get(Peak, date.today())
        return jsonify({
            'today': today.today if today else 0,
            'yesterday': today.yesterday if today else 0
        })
    finally:
        session.close()

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
